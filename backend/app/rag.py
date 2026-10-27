"""
RAG core: ingestion (load -> split -> embed -> store) and
question answering (retrieve -> augment -> generate -> cite).
"""
import hashlib
import math
import re
import os
from collections import Counter
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")  # silence chromadb telemetry noise
from pathlib import Path
from typing import List

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import settings

SUPPORTED_EXT = {".pdf", ".txt", ".md"}

_embeddings = None
_vectorstore = None
_llm = None
_bm25 = None

# bge models are trained to receive this prefix on QUESTIONS (not on documents) for retrieval.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class QueryPrefixedEmbeddings(Embeddings):
    """Wraps an embedding model and adds an instruction prefix to queries only."""

    def __init__(self, base: Embeddings, prefix: str):
        self.base, self.prefix = base, prefix

    def embed_documents(self, texts):
        return self.base.embed_documents(texts)

    def embed_query(self, text):
        return self.base.embed_query(self.prefix + text)


# ---------- lazy singletons (models load once, not per request) ----------

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        base = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            # bge models work best with normalized vectors (cosine similarity)
            encode_kwargs={"normalize_embeddings": True},
        )
        _embeddings = (QueryPrefixedEmbeddings(base, BGE_QUERY_PREFIX)
                       if "bge" in settings.EMBEDDING_MODEL.lower() else base)
    return _embeddings


def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = Chroma(
            collection_name=settings.COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=settings.CHROMA_DIR,
            collection_metadata={"hnsw:space": "cosine"},
        )
    return _vectorstore


def get_llm():
    global _llm
    if _llm is None:
        if not settings.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is not set in backend/.env")
        _llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.2,  # low temperature = fewer creative (hallucinated) answers
        )
    return _llm


# ---------- ingestion ----------

def load_file(path: Path, category: str) -> List[Document]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        docs = PyPDFLoader(str(path)).load()
    elif ext in {".txt", ".md"}:
        docs = TextLoader(str(path), encoding="utf-8").load()
    else:
        return []

    # pages saved by scrape_website.py start with <!-- source_url: ... -->
    url = ""
    if ext == ".md" and docs:
        m = re.match(r"<!--\s*source_url:\s*(\S+)\s*-->", docs[0].page_content)
        if m:
            url = m.group(1)
            docs[0].page_content = docs[0].page_content[m.end():].lstrip()

    for d in docs:
        d.metadata["source"] = path.name
        d.metadata["category"] = category
        d.metadata["url"] = url
        # PyPDF pages are 0-indexed; show 1-indexed to users
        if "page" in d.metadata:
            d.metadata["page"] = int(d.metadata["page"]) + 1
    return docs


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _pretty_name(filename: str) -> str:
    """'wp_content_uploads_2026_02_Mandatory_Disclosure_2026.pdf' -> 'Mandatory Disclosure 2026'"""
    stem = Path(filename).stem
    stem = re.sub(r"^wp_content_uploads_\d{4}_\d{2}_", "", stem)
    return re.sub(r"[_\-]+", " ", stem).strip()


def _md_sections(text: str, title: str):
    """Split markdown into (breadcrumb, body) sections, e.g. ('Fee Details > 2025 Batch', '| CSE | ...')."""
    sections, buf, path = [], [], {}
    crumb = title

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append((crumb, body))

    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            flush()
            buf = []
            level, heading = len(m.group(1)), m.group(2)
            path = {lv: h for lv, h in path.items() if lv < level}
            path[level] = heading
            parts = [title] + [path[lv] for lv in sorted(path) if path[lv] != title]
            crumb = " > ".join(parts)
        else:
            buf.append(line)
    flush()
    return sections


def split_documents(docs: List[Document]) -> List[Document]:
    """Chunk documents and prefix every chunk with where it came from (contextual chunk headers).

    Why: a chunk like '| CSE | 120000 | 3000 |' has almost no meaning on its own. Prefixing it with
    'Fee Details > 2025 Batch' lets both the embedding model and keyword search match it to
    'What is the CSE fee for the 2025 batch?'.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    out = []
    for d in docs:
        src = d.metadata.get("source", "")
        if src.lower().endswith(".md"):
            text = d.page_content
            first = text.lstrip().splitlines()[0] if text.strip() else ""
            m = HEADING_RE.match(first)
            title = m.group(2) if m else _pretty_name(src)
            text = re.sub(r"^Source:\s*\S+\s*$", "", text, flags=re.M)  # url line is noise for search
            sections = _md_sections(text, title)
        else:
            label = _pretty_name(src)
            if d.metadata.get("page"):
                label += f" (page {d.metadata['page']})"
            sections = [(label, d.page_content)]

        for crumb, body in sections:
            for piece in splitter.split_text(body):
                if piece.strip():
                    out.append(Document(page_content=f"{crumb}\n{piece}", metadata=dict(d.metadata)))
    return out


def _chunk_id(chunk: Document) -> str:
    """Deterministic ID so re-ingesting the same file updates instead of duplicating."""
    key = f"{chunk.metadata.get('source')}|{chunk.metadata.get('page', 0)}|{chunk.page_content}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def delete_source(filename: str) -> None:
    global _bm25
    _bm25 = None
    vs = get_vectorstore()
    existing = vs.get(where={"source": filename})
    if existing and existing.get("ids"):
        vs.delete(ids=existing["ids"])


def ingest_file(path: Path, category: str = "general") -> int:
    docs = load_file(path, category)
    if not docs:
        return 0
    chunks = split_documents(docs)
    chunks = [c for c in chunks if c.page_content.strip()]
    if not chunks:
        return 0

    delete_source(path.name)  # replace old version of the same file
    ids = [_chunk_id(c) for c in chunks]
    # de-duplicate identical chunks within the file
    unique = {}
    for i, c in zip(ids, chunks):
        unique[i] = c
    get_vectorstore().add_documents(list(unique.values()), ids=list(unique.keys()))
    global _bm25
    _bm25 = None
    return len(unique)


def ingest_directory(root: str = None) -> dict:
    """Walk data/ — each sub-folder name becomes the document category."""
    root_path = Path(root or settings.DATA_DIR)
    report = {}
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXT:
            continue
        if path.name.lower() == "readme.md":
            continue
        category = path.parent.name if path.parent != root_path else "general"
        if category == "uploads":
            category = "general"
        n = ingest_file(path, category)
        report[str(path.relative_to(root_path))] = n
        print(f"  ingested {path.name:<45} [{category}] -> {n} chunks")
    return report


# ---------- hybrid retrieval: BM25 keywords + vector meaning ----------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = set("""a an the is are was were be of to in on for and or what which who whom how when where why
do does did can could i me my we our you your its this that these those with from by at as about
please tell give list any there their them he she his her than then so if not no yes""".split())


def _tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]


class BM25:
    """Okapi BM25 keyword ranking — the classic search-engine formula.

    Scores a chunk higher when it contains the query's words, especially rare words
    (e.g. 'tuition', 'cse', '2025'), with diminishing returns for repeats and a penalty for very long chunks.
    """

    def __init__(self, docs: List[Document], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.tfs = [Counter(_tokenize(d.page_content)) for d in docs]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avgdl = (sum(self.lens) / len(self.lens)) if self.lens else 1.0
        df = Counter(t for tf in self.tfs for t in tf)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int, category: str = None) -> List[Document]:
        q = set(_tokenize(query))
        scored = []
        for i, tf in enumerate(self.tfs):
            if category and self.docs[i].metadata.get("category") != category:
                continue
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avgdl))
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [self.docs[i] for _, i in scored[:k]]


def get_bm25() -> BM25:
    """Built from everything in ChromaDB; rebuilt automatically when the chunk count changes."""
    global _bm25
    vs = get_vectorstore()
    count = vs._collection.count()
    if _bm25 is None or _bm25[0] != count:
        data = vs.get(include=["documents", "metadatas"])
        docs = [Document(page_content=t, metadata=m or {}) for t, m in zip(data["documents"], data["metadatas"])]
        _bm25 = (count, BM25(docs))
    return _bm25[1]


def _doc_key(d: Document) -> str:
    return hashlib.sha1(f"{d.metadata.get('source')}|{d.metadata.get('page')}|{d.page_content}".encode()).hexdigest()


def retrieve(question: str, category: str = None, k: int = None, debug: bool = False):
    """Reciprocal Rank Fusion of vector search and BM25: a chunk ranked high by EITHER method rises to the top."""
    k = k or settings.TOP_K
    cat = category if category and category != "all" else None
    pool = k * 4

    vec = get_vectorstore().similarity_search(question, k=pool, filter={"category": cat} if cat else None)
    kw = get_bm25().search(question, pool, cat)

    scores, by_key, found_by = {}, {}, {}
    for name, results in (("vector", vec), ("keyword", kw)):
        for rank, d in enumerate(results):
            key = _doc_key(d)
            by_key[key] = d
            scores[key] = scores.get(key, 0.0) + 1.0 / (60 + rank)   # RRF, k=60 is the standard constant
            found_by.setdefault(key, []).append(f"{name}#{rank + 1}")

    ranked = sorted(scores, key=scores.get, reverse=True)
    picked, per_source = [], Counter()
    for key in ranked:                       # max 3 chunks from one file, so one huge page can't take every slot
        src = by_key[key].metadata.get("source")
        if per_source[src] >= 3:
            continue
        per_source[src] += 1
        picked.append(key)
        if len(picked) == k:
            break

    docs = [by_key[key] for key in picked]
    if debug:
        return docs, [found_by[key] for key in picked]
    return docs


# ---------- question answering ----------

SYSTEM_PROMPT = """You are CampusAI, the official information assistant for the college.
Answer the user's question using ONLY the context below, which comes from verified college documents.

Rules:
- If the answer is not in the context, say: "I couldn't find that in the official college documents. Please contact the college office for this information." Do not guess.
- Quote exact figures (fees, dates, percentages, cut-offs) exactly as written in the context.
- Be concise and clear. Use bullet points for lists.
- Cite the sources you used inline like [1], [2] matching the numbered context blocks.

Context:
{context}"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("placeholder", "{history}"),
    ("human", "{question}"),
])


def _format_context(docs: List[Document]) -> str:
    blocks = []
    for i, d in enumerate(docs, start=1):
        src = d.metadata.get("source", "unknown")
        page = d.metadata.get("page")
        label = f"{src}, page {page}" if page else src
        blocks.append(f"[{i}] (Source: {label})\n{d.page_content}")
    return "\n\n".join(blocks)


def answer_question(question: str, history: list = None, category: str = None) -> dict:
    docs = retrieve(question, category)

    if not docs:
        return {
            "answer": "The knowledge base is empty or has nothing relevant yet. Please ask an admin to upload college documents.",
            "sources": [],
        }

    # convert last few turns into chat messages for follow-up questions ("what about for CSE?")
    msgs = []
    for turn in (history or [])[-4:]:
        msgs.append(("human", turn.get("question", "")))
        msgs.append(("ai", turn.get("answer", "")))

    chain = prompt | get_llm()
    result = chain.invoke({
        "context": _format_context(docs),
        "history": msgs,
        "question": question,
    })

    sources = []
    for i, d in enumerate(docs, start=1):
        sources.append({
            "id": i,
            "source": d.metadata.get("source"),
            "page": d.metadata.get("page"),
            "category": d.metadata.get("category"),
            "url": d.metadata.get("url") or None,
            "snippet": d.page_content[:220].strip() + ("..." if len(d.page_content) > 220 else ""),
        })

    content = result.content
    if isinstance(content, list):  # some Gemini responses come as content parts
        content = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)

    return {"answer": content, "sources": sources}


def collection_stats() -> dict:
    vs = get_vectorstore()
    data = vs.get(include=["metadatas"])
    per_source = {}
    for m in data.get("metadatas", []):
        s = m.get("source", "unknown")
        per_source[s] = per_source.get(s, 0) + 1
    return {"total_chunks": len(data.get("ids", [])), "per_source": per_source} 