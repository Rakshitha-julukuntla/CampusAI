"""
Crawl the college website and save its content into data/<category>/ for ingestion.

What it does
  - Visits every page on the same domain (breadth-first, up to --max-pages)
  - Strips menus/headers/footers/scripts, keeps headings, paragraphs, lists and TABLES
  - Saves each page as a .md file with its source URL (shown as a clickable citation in the chat)
  - Downloads every linked PDF (brochures, syllabus, fee structure, regulations, circulars)
  - Auto-sorts files into category folders using keywords in the URL/title
  - Respects robots.txt, waits between requests, skips duplicate pages

Usage (from backend/ with venv active):
    python scrape_website.py https://your-college-website.edu.in
    python scrape_website.py https://your-college-website.edu.in --max-pages 300 --delay 1
    python scrape_website.py https://your-college-website.edu.in --no-pdfs
    python scrape_website.py https://your-college-website.edu.in/some-page/ --test
Then review data/scrape_report.csv, delete junk, and run:  python ingest.py
"""
import argparse
import csv
import hashlib
import re
import time
from collections import Counter, deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data"
# Many college sites sit behind Cloudflare, which rejects obvious bot user-agents.
# We identify as a normal browser plus our project name, and still obey robots.txt + a polite delay.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 CampusAI-StudentProject/1.1"),
    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}
ROBOTS_AGENT = "CampusAI-StudentProject"

# First matching category wins, so specific ones come first.
CATEGORY_KEYWORDS = {
    "fees": ["fee", "fees", "scholarship", "reimbursement", "payment", "refund"],
    "admissions": ["admission", "eligibility", "eamcet", "eapcet", "ecet", "pgecet", "intake", "counselling", "prospectus", "brochure"],
    "examinations": ["exam", "examination", "result", "revaluation", "supplementary", "timetable", "time-table", "grading", "cgpa", "hall-ticket"],
    "placements": ["placement", "recruit", "career", "training", "internship", "tpo", "t-p", "mou"],
    "academics": ["syllabus", "curriculum", "regulation", "r22", "r23", "r25", "academic", "calendar", "course-structure", "elective", "nptel"],
    "policies": ["policy", "policies", "conduct", "ragging", "grievance", "committee", "icc", "attendance", "rules"],
    "facilities": ["library", "hostel", "transport", "bus", "lab", "sports", "canteen", "infrastructure", "facilit", "medical", "gym"],
    "student_life": ["club", "event", "fest", "nss", "ncc", "cultural", "chapter", "student-activit", "hackathon", "gallery"],
    "departments": ["department", "dept", "cse", "ece", "eee", "aiml", "ai-ml", "faculty", "hod", "civil", "mech"],
    "notices": ["notice", "circular", "news", "announcement", "notification", "latest"],
}

# WordPress URLs that are duplicates/noise for a knowledge base
SKIP_PATTERNS = ("/wp-json", "/feed", "/wp-login", "/wp-admin", "/xmlrpc", "/tag/", "/author/",
                 "replytocom=", "/comment-page-", "?share=", "/attachment/", "/cdn-cgi/", "?s=", "/page/")

SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".mp4", ".mp3", ".zip", ".rar",
            ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".css", ".js", ".xml", ".json")


def categorize(url: str, title: str = "") -> str:
    text = (urlparse(url).path + " " + title).lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        if any(w in text for w in words):
            return cat
    return "general"


def safe_filename(url: str, ext: str) -> str:
    path = urlparse(url).path.strip("/") or "home"
    path = re.sub(r"\.(html?|php|aspx?|pdf)$", "", path, flags=re.I)
    name = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_")[:90] or "page"
    return f"{name}{ext}"


def table_to_markdown(table) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)).replace("|", "/")
                 for c in tr.find_all(["th", "td"])]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


BLOCK_TAGS = {"p", "div", "section", "article", "main", "li", "ul", "ol", "dl", "dt", "dd", "blockquote",
              "pre", "figcaption", "h1", "h2", "h3", "h4", "h5", "h6", "table", "header", "footer", "aside", "nav"}
LEAF_TAGS = ["p", "div", "section", "li", "dt", "dd", "blockquote", "pre", "figcaption",
             "h1", "h2", "h3", "h4", "h5", "h6", "table"]
BOILERPLATE = ["nav", "header", "footer", "aside", "form", '[class*="menu"]', '[id*="menu"]', '[class*="navbar"]',
               '[class*="footer"]', '[class*="breadcrumb"]', '[class*="social"]', '[class*="cookie"]',
               '[class*="share"]', '[role="navigation"]', '[class*="skip-link"]', '[class*="screen-reader"]']
# Most-specific first: Elementor page body, WordPress post body, then generic containers
MAIN_CANDIDATES = ['[data-elementor-type="wp-page"]', '[data-elementor-type="wp-post"]',
                   '[data-elementor-type="single-page"]', '[data-elementor-type="single-post"]',
                   '[data-elementor-type="single"]', ".entry-content", "main", "article", '[role="main"]',
                   "#content", "#main"]
JUNK_LINES = re.compile(r"^(read more|click here|learn more|know more|view more|view all|apply now|"
                        r"download|more|submit|search|menu|close|toggle navigation|skip to content)$", re.I)


def _words(el) -> int:
    return len(el.get_text(" ", strip=True).split())


def pick_main(soup: BeautifulSoup):
    """Choose the element that holds the page's real content."""
    body = soup.body or soup
    for sel in MAIN_CANDIDATES:
        for el in soup.select(sel):
            if _words(el) >= 30:
                return el
    return body


def html_to_markdown(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "template", "button", "select"]):
        tag.decompose()

    main = pick_main(soup)
    total = max(_words(main), 1)

    # Remove menus/headers/footers INSIDE the content area — but never something that holds most of
    # the page (some themes put "menu" in classes of big wrappers; deleting those wiped whole pages).
    for sel in BOILERPLATE:
        for tag in main.select(sel):
            if tag is main or tag.parent is None:
                continue
            if _words(tag) < 0.5 * total:
                tag.decompose()

    out = []
    for el in main.find_all(LEAF_TAGS):
        if el.name != "table" and el.find_parent("table"):
            continue                      # cells are handled by their table
        if el.name == "table":
            md = table_to_markdown(el)
            if md:
                out.append(md)
            continue
        has_block_children = el.find(lambda t: t.name in BLOCK_TAGS) is not None
        if has_block_children:
            # keep only text written directly inside this element (children are visited separately)
            text = " ".join(t.strip() for t in el.find_all(string=True, recursive=False) if t.strip())
        else:
            text = el.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 3 or JUNK_LINES.match(text):
            continue
        if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            out.append("#" * min(int(el.name[1]), 4) + " " + text)
        elif el.name in ("li", "dt"):
            out.append("- " + text)
        else:
            out.append(text)

    # drop repeated lines (Elementor often renders the same block twice for desktop/mobile)
    seen, cleaned = set(), []
    for line in out:
        if line not in seen:
            seen.add(line)
            cleaned.append(line)
    return "\n\n".join(cleaned)


def main():
    ap = argparse.ArgumentParser(description="Scrape college website into the CampusAI knowledge base")
    ap.add_argument("url", help="College website home page, e.g. https://www.yourcollege.edu.in")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (be polite)")
    ap.add_argument("--min-words", type=int, default=40, help="skip pages with less text than this")
    ap.add_argument("--no-pdfs", action="store_true", help="don't download linked PDFs")
    ap.add_argument("--verbose", action="store_true", help="print every skipped URL and why")
    ap.add_argument("--test", action="store_true",
                    help="only fetch the given URL and print what would be extracted (nothing saved)")
    args = ap.parse_args()

    if args.test:
        r = requests.get(args.url, headers=HEADERS, timeout=30)
        print(f"HTTP {r.status_code}  Content-Type: {r.headers.get('Content-Type')}  Size: {len(r.text)} chars")
        soup = BeautifulSoup(r.text, "html.parser")
        body = html_to_markdown(soup)
        print(f"Extracted {len(body.split())} words  (min needed: {args.min_words})\n" + "-" * 60)
        print(body[:3000] + ("\n... [truncated]" if len(body) > 3000 else ""))
        return

    start = args.url.rstrip("/")
    domain = urlparse(start).netloc.replace("www.", "")

    session = requests.Session()
    session.headers.update(HEADERS)

    # Fetch robots.txt ourselves. Python's RobotFileParser.read() uses a bare urllib user-agent;
    # Cloudflare answers that with 403, which RobotFileParser treats as "disallow everything"
    # -> silently 0 pages. Per RFC 9309, a 4xx on robots.txt means "no rules", 5xx means "don't crawl".
    robots_url = f"{urlparse(start).scheme}://{urlparse(start).netloc}/robots.txt"
    robots = RobotFileParser()
    try:
        rr = session.get(robots_url, timeout=20)
        if rr.status_code == 200:
            robots.parse(rr.text.splitlines())
            print(f"robots.txt loaded ({len(rr.text.splitlines())} lines)")
        elif 400 <= rr.status_code < 500:
            robots = None
            print(f"robots.txt returned {rr.status_code} -> no crawl rules")
        else:
            print(f"robots.txt returned {rr.status_code} -> server problem, try again later")
            return
    except requests.RequestException as e:
        robots = None
        print(f"robots.txt not reachable ({e.__class__.__name__}) -> no crawl rules")

    queue, seen, seen_hashes, report = deque([start]), {start}, set(), []
    pages = 0
    skipped = Counter()
    print(f"Crawling {start} (max {args.max_pages} pages)...\n")

    while queue and pages < args.max_pages:
        url = queue.popleft()
        if robots and not robots.can_fetch(ROBOTS_AGENT, url):
            skipped["blocked by robots.txt"] += 1
            if args.verbose:
                print(f"  - robots.txt disallows {url}")
            continue
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException as e:
            skipped["network error"] += 1
            print(f"  ! failed {url}: {e.__class__.__name__}")
            continue
        time.sleep(args.delay)
        if r.status_code != 200:
            skipped[f"HTTP {r.status_code}"] += 1
            print(f"  ! HTTP {r.status_code}  {url}")
            if url == start and r.status_code in (403, 503) and "cloudflare" in r.headers.get("Server", "").lower():
                print("\n  The site's Cloudflare protection is blocking scripts. See README -> 'Scraping the website'.")
            continue
        ctype = r.headers.get("Content-Type", "").lower()

        # ---------- PDF ----------
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            if args.no_pdfs:
                continue
            h = hashlib.md5(r.content).hexdigest()
            if h in seen_hashes or not r.content.startswith(b"%PDF"):
                continue
            seen_hashes.add(h)
            cat = categorize(url)
            dest = DATA_DIR / cat / safe_filename(url, ".pdf")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            report.append([cat, dest.name, "pdf", len(r.content) // 1024, url])
            print(f"  PDF  [{cat:<12}] {dest.name}")
            continue

        if "html" not in ctype:
            continue
        pages += 1

        # ---------- HTML page ----------
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link, _ = urldefrag(urljoin(url, a["href"].strip()))
            p = urlparse(link)
            if p.scheme not in ("http", "https") or p.netloc.replace("www.", "") != domain:
                continue
            if link.lower().endswith(SKIP_EXT) or "mailto:" in link or "javascript:" in link \
                    or any(sp in link.lower() for sp in SKIP_PATTERNS):
                continue
            link = link.rstrip("/")
            if link not in seen:
                seen.add(link)
                # PDFs first: they usually hold the most valuable info
                (queue.appendleft if link.lower().endswith(".pdf") else queue.append)(link)

        title = soup.title.get_text(strip=True) if soup.title else ""
        body = html_to_markdown(soup)
        words = len(body.split())
        if words < args.min_words:
            skipped["too little text"] += 1
            if args.verbose:
                print(f"  - only {words} words, skipped {url}")
            continue
        h = hashlib.md5(body.encode()).hexdigest()
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        cat = categorize(url, title)
        dest = DATA_DIR / cat / safe_filename(url, ".md")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f"<!-- source_url: {url} -->\n# {title}\n\nSource: {url}\n\n{body}\n", encoding="utf-8")
        report.append([cat, dest.name, "page", words, url])
        print(f"  PAGE [{cat:<12}] {dest.name}  ({words} words)")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    report_path = DATA_DIR / "scrape_report.csv"
    rows = {(r[0], r[1]): r for r in report}
    if report_path.exists():  # keep earlier rows (e.g. PDFs from a previous run) whose files still exist
        with open(report_path, newline="", encoding="utf-8") as f:
            for r in list(csv.reader(f))[1:]:
                if len(r) == 5 and (r[0], r[1]) not in rows and (DATA_DIR / r[0] / r[1]).exists():
                    rows[(r[0], r[1])] = r
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "file", "type", "words_or_kb", "url"])
        w.writerows(sorted(rows.values()))

    n_pdf = sum(1 for r in report if r[2] == "pdf")
    if skipped:
        print("\nSkipped: " + ", ".join(f"{k}: {v}" for k, v in skipped.most_common()))
    print(f"\nDone: {len(report) - n_pdf} pages + {n_pdf} PDFs saved into {DATA_DIR}")
    print(f"Review {report_path} — move mis-sorted files, delete junk — then run:  python ingest.py")
    if len(report) - n_pdf < 3:
        print("\nVery few pages captured. The site may load content with JavaScript; see README → 'Scraping the website'.")


if __name__ == "__main__":
    main()