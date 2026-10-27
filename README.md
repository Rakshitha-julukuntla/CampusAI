# CampusAI — Intelligent College Information System

RAG chatbot that answers questions about the college from verified documents, with source citations.

**Stack:** Python · FastAPI · React.js (Vite) · MySQL · ChromaDB · LangChain · Gemini 2.5 Flash · BAAI/bge-small · PyPDF · RecursiveCharacterTextSplitter · JWT

```
campusai/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, startup (tables + admin user)
│   │   ├── config.py        # reads .env
│   │   ├── database.py      # SQLAlchemy + MySQL
│   │   ├── models.py        # users, chat_history, documents tables
│   │   ├── auth.py          # bcrypt hashing + JWT create/verify
│   │   ├── rag.py           # load → split → embed → Chroma; retrieve → Gemini → cite
│   │   └── routers/         # /api/auth, /api/chat, /api/documents
│   ├── data/                # ← put college documents here (one folder per category)
│   ├── ingest.py            # bulk-index everything in data/
│   ├── schema.sql           # creates the MySQL database
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/pages/           # Login, Register, Chat, Admin
```

## How it works

1. **Ingestion** — PyPDF/TextLoader reads each file → RecursiveCharacterTextSplitter cuts it into ~800-char chunks with 150 overlap → bge-small turns each chunk into a 384-dim vector → stored in ChromaDB with `source`, `page`, `category` metadata.
2. **Query** — user question is embedded with the same model → ChromaDB returns top-5 chunks (MMR for diversity, optional category filter).
3. **Generation** — chunks are numbered `[1]..[5]` and put in a strict prompt → Gemini 2.5 Flash answers *only* from that context and cites `[n]`; says "not found" otherwise.
4. **Response** — answer + source list (file, page, snippet) shown in the UI; Q&A saved to MySQL.

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | **3.10 – 3.12** (recommended 3.11) | `python --version` |
| Node.js | 18+ | `node --version` |
| MySQL Server | 8.x | `mysql --version` |
| Gemini API key | free | https://aistudio.google.com/app/apikey |

## Run it — step by step

### 1. Create the MySQL database
```bash
mysql -u root -p < backend/schema.sql
```
(or open MySQL Workbench and run `CREATE DATABASE campusai;`)

### 2. Backend setup
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

Copy the env file and edit it:
```bash
# Windows:  copy .env.example .env
cp .env.example .env
```
Set at minimum: `GOOGLE_API_KEY`, `DATABASE_URL` (your MySQL password), `JWT_SECRET`.

### 3. Add documents & build the knowledge base

**Option A — scrape your college website (fastest):**
```bash
python scrape_website.py https://your-college-website.edu.in --max-pages 300
```
This saves every page as `.md` (menus/footers stripped, tables kept) and downloads every linked PDF into `data/<category>/`.
Then open `data/scrape_report.csv`, move any mis-sorted files to the right folder, delete junk pages (gallery, login, empty), and run:
```bash
python ingest.py
```
Scraped pages show their original web link as the citation in the chat.

**Option B — add files manually:**
Put PDFs / .txt / .md into `backend/data/<category>/` (see `backend/data/README.md`), then:
```bash
python ingest.py
```
First run downloads the bge-small model (~130 MB). A `SAMPLE_college_faq.md` is included so you can test immediately — delete it before the demo.

### 4. Start the backend
```bash
uvicorn app.main:app --reload --port 8000
```
Check: http://localhost:8000/api/health and API docs at http://localhost:8000/docs

### 5. Start the frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

### 6. Use it
- **Admin login:** `admin@campusai.in` / `admin123` (from `.env`) → Admin page → upload PDFs, pick category, re-index.
- **Students/parents/faculty:** Register → Chat. Try "What is the attendance requirement?"

## API endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | – | create student/parent/faculty account |
| POST | `/api/auth/login` | – | form `username`(email) + `password` → JWT |
| GET | `/api/auth/me` | user | current user |
| POST | `/api/chat` | user | `{question, category}` → `{answer, sources}` |
| GET / DELETE | `/api/chat/history` | user | load / clear history |
| GET | `/api/documents/categories` | – | category list |
| GET | `/api/documents` | admin | list indexed docs |
| POST | `/api/documents/upload` | admin | multipart `file` + `category` |
| DELETE | `/api/documents/{id}` | admin | remove doc + its vectors |
| POST | `/api/documents/reindex` | admin | re-ingest data/ folder |
| GET | `/api/documents/stats` | admin | chunk counts |

## Scraping the website — notes
- If only a few pages are captured, the site probably loads content with JavaScript. Fix: save those pages from the browser (Ctrl+P → Save as PDF) into the right `data/` folder.
- Login-only portals (results, attendance ERP) can't be scraped — and shouldn't be; they hold personal data.
- Images of notices (JPG circulars) have no text — download, OCR, or retype the important ones as `.md`.
- Re-run the scraper each semester to refresh content, then `python ingest.py`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Access denied for user 'root'` | wrong password in `DATABASE_URL` |
| `Unknown database 'campusai'` | run step 1 |
| `GOOGLE_API_KEY is not set` | add key to `backend/.env`, restart uvicorn |
| `429 / quota exceeded` from Gemini | free-tier rate limit — wait a minute |
| Upload says "no text could be extracted" | scanned PDF → OCR it (`ocrmypdf in.pdf out.pdf`) |
| Bot answers "couldn't find" for things that exist | check `/api/documents/stats`; try smaller `CHUNK_SIZE` or larger `TOP_K` |
| pip fails building chromadb/torch | use Python 3.11 |
| Want a fresh vector DB | `python ingest.py --reset` |

## Tuning knobs (`.env`)
- `CHUNK_SIZE` / `CHUNK_OVERLAP` — smaller chunks = more precise retrieval, less context per chunk.
- `TOP_K` — how many chunks go to Gemini. 4–6 is a good range.
- `temperature=0.2` in `rag.py` — kept low so answers stick to documents.
