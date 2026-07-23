import os
import re
import json
import time
import unicodedata
import requests
from pathlib import Path
from datetime import datetime, date
from sqlalchemy import case
from sqlalchemy.orm import Session
from google.genai import types

from database import DATA_DIR, SessionLocalCA
from models import CurrentAffairs, CuratedCA, TrendMetrics
from api_guardrail import protected_gemini_call
import hashlib

RELEVANCE_ORDER = case(
    (CurrentAffairs.upsc_relevance == "high", 0),
    (CurrentAffairs.upsc_relevance == "medium", 1),
    (CurrentAffairs.upsc_relevance == "low", 2),
    else_=3,
)

RSS_FEEDS = {
    "the_hindu":              "https://www.thehindu.com/feeder/default.rss",
    "indianexpress_editorials": "https://indianexpress.com/section/opinion/editorials/feed",
    "indianexpress_explained":  "https://indianexpress.com/section/explained/feed",
    "ndtv":                   "https://feeds.feedburner.com/ndtvnews-india-news",
    "ht_india":               "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
    "et_india":               "https://economictimes.indiatimes.com/news/india/rssfeeds/13352306.cms",
    "pib":                    "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
}



def _fetch_rss(url: str) -> list[dict]:
    import feedparser
    import time as time_module
    feed = feedparser.parse(url)
    entries = []
    for e in feed.entries:
        pub_ts = None
        if hasattr(e, "published_parsed") and e.published_parsed:
            pub_ts = datetime(*e.published_parsed[:6])
        entries.append({
            "title": e.get("title", ""),
            "link": e.get("link", ""),
            "summary": e.get("summary", "")[:300],
            "published": e.get("published", ""),
            "published_parsed": pub_ts,
        })
    return entries


def _title_similarity(a: str, b: str) -> float:
    a_words = set(a.lower().split()[:8])
    b_words = set(b.lower().split()[:8])
    if not a_words or not b_words:
        return 0.0
    intersection = a_words & b_words
    return len(intersection) / max(len(a_words), len(b_words))


def _dedup(entries: list[dict]) -> list[dict]:
    """Remove near-duplicates by title similarity > 0.6."""
    kept = []
    for e in entries:
        if any(_title_similarity(e["title"], k["title"]) > 0.6 for k in kept):
            continue
        kept.append(e)
    return kept


def _download_image(url: str, entry_id: int) -> str | None:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 5000:
            ext = url.split(".")[-1].split("?")[0]
            if ext not in ("jpg", "jpeg", "png", "webp"):
                ext = "jpg"
            img_dir = DATA_DIR / "ca_images"
            img_dir.mkdir(exist_ok=True)
            path = str(img_dir / f"{entry_id}.{ext}")
            with open(path, "wb") as f:
                f.write(r.content)
            return path
    except Exception:
        pass
    return None


def _pick_best_image(title: str, image_urls: set[str]) -> str | None:
    """Use Gemini to pick the most topic-relevant image from a set of URLs."""
    if not image_urls:
        return None
    candidates = [u for u in image_urls if u and u.startswith("http")]
    if not candidates:
        return None
    # Filter out obvious logos/icons by URL pattern
    skip_patterns = ("logo", "icon", "sprite", "avatar", "button", "banner", "favicon", "badge")
    filtered = [u for u in candidates if not any(p in u.lower() for p in skip_patterns)]
    if not filtered:
        return None
    if len(filtered) == 1:
        return filtered[0]
    try:
        import re
        resp = protected_gemini_call("ca_parser", lambda c, m: c.models.generate_content(
            model=m,
            contents=f"""Given this news article title, which image URL best illustrates the topic?

Title: {title}

Image URLs:
{chr(10).join(f'{i}. {u}' for i, u in enumerate(filtered[:10]))}

Return the index number (0-based) of the most topic-relevant image. Return ONLY a number.""",
            config=types.GenerateContentConfig(max_output_tokens=16, temperature=0.1),
        ))
        text = (resp.text or "").strip()
        match = re.search(r'\d+', text)
        if match:
            idx = int(match.group())
            if 0 <= idx < len(filtered):
                return filtered[idx]
    except Exception:
        pass
    return filtered[0]


PARSE_PROMPT = """\
You are a UPSC current affairs analyst. Analyze this news article.

Return JSON with:
- title: string
- summary: 150-200 words covering what happened, WHY it happened (context), and relevant historical background
- category: one of Polity/Economy/Geography/Environment/Science/International/Social/Culture/Security
- subject: one of Polity/History/Economy/Geography/Environment/Science/Culture/International Relations
- tags: array of 5-10 keywords
- key_facts: array of important facts, data points, committee names, dates
- upsc_relevance: high/medium/low
- historical_context: 2-3 sentences of relevant history — what led to this, previous similar events
- date_of_event: string or null

Article:
{article_text}
"""


def _parse_article(title: str, full_text: str, source_url: str, source: str) -> dict:
    """Structure a single article using 3.1 Flash Lite."""
    if len(full_text) > 8000:
        full_text = full_text[:8000]

    prompt = PARSE_PROMPT.format(article_text=f"{title}\n\n{full_text}")

    try:
        resp = protected_gemini_call("ca_parser", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=8192),
        ))
        text = (resp.text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()
        import re
        data = json.loads(re.sub(r'[\x00-\x1f]', '', text))
    except Exception:
        data = {
            "title": title,
            "summary": full_text[:300],
            "category": "General",
            "subject": "GS",
            "tags": [],
            "key_facts": [],
            "upsc_relevance": "medium",
            "historical_context": "",
            "date_of_event": None,
        }

    return data


BATCH_PARSE_PROMPT = """You are a UPSC current affairs analyst. Analyze the following news articles in full depth.

For each article, return JSON with:
- title: string
- summary: 150-200 words covering what happened, WHY it happened, and relevant background
- category: one of Polity/Economy/Geography/Environment/Science/International/Social/Culture/Security
- subject: one of Polity/History/Economy/Geography/Environment/Science/Culture/International Relations
- tags: array of 5-10 keywords
- key_facts: array of important facts, data points, committee names, dates
- supporting_arguments: array of 2-3 key arguments supporting the policy/judgment/decision
- counter_arguments: array of 1-2 counterarguments or criticisms
- way_forward: array of 1-2 recommended future actions or implications
- upsc_relevance: high/medium/low
- historical_context: 2-3 sentences of relevant history
- date_of_event: string or null

Articles (JSON array, each has article_id, title, full_text):
{articles}

Return a JSON array of objects in the SAME ORDER as input, each with:
- article_id: int (matches input)
- title: string
- summary: string
- category: string
- subject: string
- tags: array of strings
- key_facts: array of strings
- supporting_arguments: array of strings
- counter_arguments: array of strings
- way_forward: array of strings
- upsc_relevance: string
- historical_context: string
- date_of_event: string or null
"""

BATCH_PARSE_BATCH_SIZE = 10


def _batch_parse_articles(entries: list[dict]) -> dict[str, dict]:
    """Batch-enriched parse up to 10 articles per call. Returns dict keyed by source_url."""
    results = {}
    for start in range(0, len(entries), BATCH_PARSE_BATCH_SIZE):
        batch = entries[start:start + BATCH_PARSE_BATCH_SIZE]
        payload = []
        for i, e in enumerate(batch):
            full_text = (e.get("full_text") or "")[:8000]
            payload.append({
                "article_id": start + i,
                "title": e["title"],
                "full_text": f"{e['title']}\n\n{full_text}",
            })
        prompt = BATCH_PARSE_PROMPT.format(
            articles=json.dumps(payload, indent=2),
        )
        try:
            print(f"  Batch parse: {len(batch)} articles", flush=True)
            resp = protected_gemini_call("ca_parser", lambda c, m: c.models.generate_content(
                model=m,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=32768),
            ))
            text = (resp.text or "").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0].strip()
            batch_results = json.loads(re.sub(r'[\x00-\x1f]', '', text))
        except Exception as exc:
            print(f"  Batch parse failed for chunk {start}: {exc}", flush=True)
            batch_results = []

        for r in batch_results:
            idx = r.get("article_id")
            if idx is None or not (0 <= idx < len(entries)):
                continue
            source_url = entries[idx].get("link")
            if source_url:
                results[source_url] = r

    return results


def get_relevant_entries(topic: str, limit: int = 5, db: Session | None = None) -> list[dict]:
    """Fetch recent high-relevance CA entries matching topic."""
    close_db = False
    if db is None:
        db = SessionLocalCA()
        close_db = True
    try:
        today = str(date.today())
        entries = db.query(CurrentAffairs).filter(
            CurrentAffairs.date_fetched == today,
            CurrentAffairs.upsc_relevance.in_(["high", "medium"]),
        ).order_by(
            RELEVANCE_ORDER,
            CurrentAffairs.created_at.desc(),
        ).limit(limit * 3).all()

        if not entries:
            entries = db.query(CurrentAffairs).order_by(
                RELEVANCE_ORDER,
                CurrentAffairs.created_at.desc(),
            ).limit(limit * 3).all()

        topic_lower = topic.lower()
        matched = []
        for e in entries:
            if topic_lower in (e.subject or "").lower() or topic_lower in (e.category or "").lower():
                matched.append(e)
            if len(matched) >= limit:
                break

        if len(matched) < limit:
            for e in entries:
                if e not in matched:
                    matched.append(e)
                if len(matched) >= limit:
                    break

        return [
            {
                "id": e.id,
                "title": e.title,
                "summary": e.summary,
                "category": e.category,
                "subject": e.subject,
                "tags": json.loads(e.tags) if e.tags else [],
                "key_facts": json.loads(e.key_facts) if e.key_facts else [],
                "upsc_relevance": e.upsc_relevance,
            }
            for e in matched[:limit]
        ]
    finally:
        if close_db:
            db.close()


def sanitize_for_pdf(text: str) -> str:
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')


def generate_digest_pdf(output_path: str, db: Session | None = None, date_filter: str | None = None):
    """Generate a formatted daily digest PDF with images."""
    from fpdf import FPDF

    close_db = False
    if db is None:
        db = SessionLocalCA()
        close_db = True
    try:
        query_date = date_filter or str(date.today())
        entries = db.query(CurrentAffairs).filter(
            CurrentAffairs.date_fetched == query_date,
        ).order_by(
            RELEVANCE_ORDER,
            CurrentAffairs.created_at.desc(),
        ).limit(20).all()

        if not entries and not date_filter:
            entries = db.query(CurrentAffairs).order_by(
                CurrentAffairs.created_at.desc(),
            ).limit(20).all()

        if not entries:
            return

        pdf = FPDF()
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=20)

        # Cover page
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 24)
        pdf.ln(40)
        pdf.cell(0, 15, "CURRENT AFFAIRS DIGEST", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 14)
        pdf.cell(0, 10, query_date, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 11)
        pdf.cell(0, 8, f"Top {len(entries)} stories curated for UPSC", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(20)
        pdf.set_font("Helvetica", "", 10)
        for i, e in enumerate(entries, 1):
            subj = e.subject or "GS"
            pdf.cell(0, 7, sanitize_for_pdf(f"  {i}. [{subj}] {e.title[:90]}"), new_x="LMARGIN", new_y="NEXT")

        # Subject sections
        subjects = ["Polity", "Economy", "International Relations", "Environment", "Science", "Geography", "Social", "Culture", "Security", "GS"]
        for subj in subjects:
            section = [e for e in entries if (e.subject or "GS") == subj]
            if not section:
                continue
            pdf.add_page()
            pdf.set_fill_color(40, 80, 160)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, f"  {subj.upper()}", fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(4)

            for s in section:
                lines = 4 + len((s.summary or "")) // 90 + 4
                if pdf.get_y() + lines * 6 > 260:
                    pdf.add_page()

                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 6, sanitize_for_pdf(s.title), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)

                # Image
                if s.image_path and Path(s.image_path).exists():
                    try:
                        img_w = 80
                        pdf.image(s.image_path, x=pdf.get_x() + 5, w=img_w)
                        pdf.ln(45)
                    except Exception:
                        pass

                badge = s.upsc_relevance or "medium"
                colors = {"high": (0, 150, 0), "medium": (180, 130, 0), "low": (150, 150, 150)}
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(*colors.get(badge, (0, 0, 0)))
                pdf.cell(0, 5, sanitize_for_pdf(f"Relevance: {badge.upper()}  |  Source: {s.source or 'Unknown'}"), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)

                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, sanitize_for_pdf(s.summary or ""), new_x="LMARGIN", new_y="NEXT")

                if s.historical_context:
                    pdf.set_font("Helvetica", "I", 9)
                    pdf.set_text_color(80, 80, 80)
                    pdf.multi_cell(0, 5, sanitize_for_pdf(f"Context: {s.historical_context}"), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(0, 0, 0)

                if s.key_facts:
                    pdf.set_font("Helvetica", "", 9)
                    try:
                        facts = json.loads(s.key_facts) if isinstance(s.key_facts, str) else s.key_facts
                        if facts:
                            pdf.ln(1)
                            for f_item in facts[:5]:
                                pdf.multi_cell(0, 5, sanitize_for_pdf(f"  - {f_item}"), new_x="LMARGIN", new_y="NEXT")
                    except Exception:
                        pass

                pdf.ln(3)

        # Tags appendix
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "TAGS & SOURCE INDEX", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        all_tags = set()
        source_index = {}
        for e in entries:
            src = e.source or "Unknown"
            source_index.setdefault(src, 0)
            source_index[src] += 1
            try:
                tags = json.loads(e.tags) if isinstance(e.tags, str) else (e.tags or [])
                for t in tags:
                    all_tags.add(t)
            except Exception:
                pass

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "Tags:", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 5, sanitize_for_pdf(", ".join(sorted(all_tags))), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.cell(0, 6, "Sources:", new_x="LMARGIN", new_y="NEXT")
        for src, count in sorted(source_index.items(), key=lambda x: x[1], reverse=True):
            pdf.cell(0, 5, sanitize_for_pdf(f"  {src}: {count} articles"), new_x="LMARGIN", new_y="NEXT")

        pdf.output(output_path)
    finally:
        if close_db:
            db.close()


def generate_curated_digest_pdf(output_path: str, db: Session | None = None, date_filter: str | None = None):
    """Generate a daily digest PDF from the CuratedCA table with enriched fields."""
    from fpdf import FPDF

    close_db = False
    if db is None:
        db = SessionLocalCA()
        close_db = True
    try:
        query_date = date_filter or str(date.today())
        entries = db.query(CuratedCA).filter(
            CuratedCA.date_fetched == query_date,
        ).order_by(
            CuratedCA.vector_match_score.desc(),
            CuratedCA.id.desc(),
        ).limit(20).all()

        if not entries and not date_filter:
            entries = db.query(CuratedCA).order_by(
                CuratedCA.id.desc(),
            ).limit(20).all()

        if not entries:
            return

        pdf = FPDF()
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=20)

        # Cover page
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 24)
        pdf.ln(40)
        pdf.cell(0, 15, "CURATED CA DIGEST", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 14)
        pdf.cell(0, 10, query_date, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 11)
        pdf.cell(0, 8, f"Top {len(entries)} stories curated for UPSC", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(20)
        pdf.set_font("Helvetica", "", 10)
        for i, e in enumerate(entries, 1):
            subj = e.gs_linkage or "GS"
            pdf.cell(0, 7, sanitize_for_pdf(f"  {i}. [{subj}] {e.title[:90]}"), new_x="LMARGIN", new_y="NEXT")

        # GS linkage sections
        linkages = ["Polity", "Economy", "International Relations", "Environment", "Science", "Geography", "Social", "Culture", "Security", "GS"]
        for linkage in linkages:
            section = [e for e in entries if (e.gs_linkage or "GS") == linkage]
            if not section:
                continue
            pdf.add_page()
            pdf.set_fill_color(40, 80, 160)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, f"  {linkage.upper()}", fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(4)

            for s in section:
                lines = 4 + len((s.summary or "")) // 90 + 8
                if pdf.get_y() + lines * 6 > 260:
                    pdf.add_page()

                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 6, sanitize_for_pdf(s.title), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)

                badge = "high" if s.vector_match_score > 0.7 else "medium"
                colors = {"high": (0, 150, 0), "medium": (180, 130, 0), "low": (150, 150, 150)}
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(*colors.get(badge, (0, 0, 0)))
                pdf.cell(0, 5, sanitize_for_pdf(f"Score: {s.vector_match_score:.2f}  |  Source: {s.source or 'Unknown'}  |  Via: {s.matched_via}"), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)

                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, sanitize_for_pdf(s.summary or ""), new_x="LMARGIN", new_y="NEXT")

                # Supporting arguments
                if s.supporting_arguments:
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.cell(0, 5, "Supporting Arguments:", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", "", 9)
                    try:
                        args = json.loads(s.supporting_arguments) if isinstance(s.supporting_arguments, str) else s.supporting_arguments
                        for a in args[:3]:
                            pdf.multi_cell(0, 5, sanitize_for_pdf(f"  + {a}"), new_x="LMARGIN", new_y="NEXT")
                    except Exception:
                        pass

                # Counter arguments
                if s.counter_arguments:
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.cell(0, 5, "Counter Arguments:", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", "", 9)
                    try:
                        args = json.loads(s.counter_arguments) if isinstance(s.counter_arguments, str) else s.counter_arguments
                        for a in args[:2]:
                            pdf.multi_cell(0, 5, sanitize_for_pdf(f"  - {a}"), new_x="LMARGIN", new_y="NEXT")
                    except Exception:
                        pass

                # Way forward
                if s.way_forward:
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.cell(0, 5, "Way Forward:", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", "", 9)
                    try:
                        wf = json.loads(s.way_forward) if isinstance(s.way_forward, str) else s.way_forward
                        for w in wf[:2]:
                            pdf.multi_cell(0, 5, sanitize_for_pdf(f"  -> {w}"), new_x="LMARGIN", new_y="NEXT")
                    except Exception:
                        pass

                # Key facts
                if s.prelims_high_yield_facts:
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.cell(0, 5, "Key Facts:", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", "", 9)
                    try:
                        facts = json.loads(s.prelims_high_yield_facts) if isinstance(s.prelims_high_yield_facts, str) else s.prelims_high_yield_facts
                        for f_item in facts[:5]:
                            pdf.multi_cell(0, 5, sanitize_for_pdf(f"  - {f_item}"), new_x="LMARGIN", new_y="NEXT")
                    except Exception:
                        pass

                pdf.ln(3)

        # Tags & sources appendix
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "TAGS & SOURCE INDEX", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        all_tags = set()
        source_index = {}
        for e in entries:
            src = e.source or "Unknown"
            source_index[src] = source_index.get(src, 0) + 1
            try:
                tags = json.loads(e.tags) if isinstance(e.tags, str) else (e.tags or [])
                for t in tags:
                    all_tags.add(t)
            except Exception:
                pass

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "Tags:", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 5, sanitize_for_pdf(", ".join(sorted(all_tags))), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.cell(0, 6, "Sources:", new_x="LMARGIN", new_y="NEXT")
        for src, count in sorted(source_index.items(), key=lambda x: x[1], reverse=True):
            pdf.cell(0, 5, sanitize_for_pdf(f"  {src}: {count} articles"), new_x="LMARGIN", new_y="NEXT")

        pdf.output(output_path)
    finally:
        if close_db:
            db.close()


ARTICLE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "full_text": {"type": "string"},
            "page_range": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
            },
            "date": {"type": "string"},
            "diagrams": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["title", "full_text", "page_range", "date", "diagrams"],
    },
}


def _extract_pdf_with_gemini(pdf_path: str) -> tuple[str, list]:
    """Send PDF directly to Gemini, get clean reformatted markdown with --- article separators.
    Returns (reformatted_markdown, list of {title, full_text}).
    Falls back to whole content on failure."""
    PROMPT = """You are given a UPSC Current Affairs PDF containing multiple distinct articles in boxes.
Your task: extract EVERY article exactly as it appears in the PDF.

Rules:
- The PDF has a fixed number of article boxes. Output EXACTLY that many articles.
- Do NOT merge articles together. Do NOT split a single article into two.
- A single article may span multiple pages — still count it as ONE article.
- Keep ALL sub-sections inside their article's full_text.
- Preserve original text exactly — do NOT summarize or reword.
- The title must NOT include the # character.
- page_range: the 1-indexed page numbers this article starts and ends on (e.g., [4, 6]).
- date: the cover date of this PDF in YYYY-MM-DD format.
- diagrams: describe any charts, maps, infographics, or images on this article's pages. Include key data points, labels, trends, and visual elements. If no diagrams exist, use an empty array.
- Output ONLY the JSON array, no explanations before or after."""

    md_dir = DATA_DIR / "markdown"
    md_dir.mkdir(exist_ok=True)
    md_path = md_dir / f"{Path(pdf_path).stem}.md"

    try:
        from google.genai import types as gtypes
        from google import genai as _genai
        print(f"  CA: Sending PDF to Gemini...", flush=True)

        client = _genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        pdf_file = client.files.upload(file=pdf_path)
        resp = protected_gemini_call("ca_restructure", lambda c, m: c.models.generate_content(
            model=m,
            contents=[PROMPT, pdf_file],
            config=gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ARTICLE_SCHEMA,
                max_output_tokens=64000,
                temperature=0.2,
                thinking_config=gtypes.ThinkingConfig(thinking_budget=12000),
            ),
        ))
        raw_json = (resp.text or "").strip()
        if not raw_json:
            raise RuntimeError("Empty response from Gemini")

        import re as _re
        sanitized = _re.sub(r'[\x00-\x1f\x7f]', '', raw_json)
        articles = json.loads(sanitized)
        if not isinstance(articles, list) or len(articles) == 0:
            raise RuntimeError("Invalid JSON response (not a non-empty array)")

        # Build markdown string from JSON articles (for downstream compatibility + debugging)
        parts = []
        for a in articles:
            title = a.get("title", "Article")
            text = a.get("full_text", "").strip()
            parts.append(f"# {title}\n\n{text}")
        markdown = "\n\n---\n\n".join(parts)

        # Save to disk for debugging
        md_path.write_text(markdown, encoding="utf-8")
        print(f"  CA: Extracted {len(articles)} articles via Gemini PDF, saved to {md_path}", flush=True)
        return markdown, articles

    except Exception as exc:
        print(f"  CA: Gemini PDF extraction failed: {exc}", flush=True)
        return "", [{"title": "Academy PDF Content", "full_text": ""}]


def clean_pyq_markdown(markdown_content: str) -> str:
    """Use ca_restructure model to remove garbled Hindi/Devanagari text from PYQ markdown.
    Returns cleaned English-only markdown. Falls back to original on failure."""
    PROMPT = """This is markdown extracted from a bilingual UPSC question paper (Hindi + English).
The Hindi/Devanagari text may be garbled, scrambled, or mixed with OCR artifacts.

Remove ALL Hindi text, Devanagari script, and garbled OCR artifacts.
Keep ONLY clean English questions with their answer options (A/B/C/D) and any English instructions.
Do NOT summarize or alter the English content — return it exactly as-is.
Return the cleaned markdown only, no explanations.

Markdown:
{markdown}"""
    try:
        from google.genai import types as gtypes
        resp = protected_gemini_call("ca_restructure", lambda c, m: c.models.generate_content(
            model=m,
            contents=PROMPT.format(markdown=markdown_content[:40000]),
            config=gtypes.GenerateContentConfig(max_output_tokens=16384),
        ))
        cleaned = (resp.text or "").strip()
        if cleaned:
            print("  PYQ: Hindi/garbled text cleaned from markdown")
            return cleaned
    except Exception as exc:
        print(f"  PYQ: Markdown cleaning failed, using original: {exc}")
    return markdown_content


def ingest_ca_pdf(pdf_path: str) -> tuple[int, list]:
    """Send PDF to Gemini for clean markdown extraction, then parse and store entries.
    Returns tuple of (stored_count, articles_list)."""

    # Step 1: Send PDF directly to Gemini -> clean markdown with --- article separators
    reformatted_md, articles = _extract_pdf_with_gemini(pdf_path)
    if not articles or not articles[0].get("full_text", "").strip():
        print("  CA: Gemini PDF extraction returned empty content")
        return 0, []

    # Step 2: Strip duplicate title from each article's full_text
    for a in articles:
        raw_title = a.get("title", "Article")
        title = raw_title.lstrip("#").strip()
        text = a.get("full_text", "").strip()
        lines = text.split('\n')
        if lines and lines[0].lstrip('#').strip() == title:
            text = '\n'.join(lines[1:]).strip()
        a["title"] = title
        a["full_text"] = text

    # Step 3: Parse and store entries in CuratedCA with priority=high
    pdf_date = str(date.today())
    for a in articles:
        if a.get("date"):
            pdf_date = a["date"]
            break

    count = 0
    db = SessionLocalCA()
    try:
        from models import CuratedCA
        for article in articles:
            title = article.get("title") or "Academy PDF Entry"
            full_text = article.get("full_text") or ""
            if not full_text.strip():
                continue
            existing = db.query(CuratedCA).filter_by(title=title, source="academy_pdf").first()
            if existing:
                continue
            try:
                parsed = _parse_article("Academy PDF", full_text, "", "academy_pdf")
            except Exception:
                parsed = {}

            entry = CuratedCA(
                issue_id=_issue_id_from_title(title),
                title=title,
                source="academy_pdf",
                source_url=f"academy_pdf://{hashlib.md5(title.encode()).hexdigest()}",
                full_text=full_text,
                summary=parsed.get("summary", full_text[:300]),
                category=parsed.get("category", "General"),
                gs_linkage=parsed.get("subject", "GS"),
                tags=json.dumps(parsed.get("tags", [])),
                supporting_arguments=json.dumps(parsed.get("supporting_arguments", [])),
                counter_arguments=json.dumps(parsed.get("counter_arguments", [])),
                way_forward=json.dumps(parsed.get("way_forward", [])),
                prelims_high_yield_facts=json.dumps(parsed.get("key_facts", [])),
                matched_via="academy",
                is_academy_verified=True,
                is_supplemental=True,
                priority="high",
                date_of_event=pdf_date,
                newspaper_name="academy_pdf",
                date_fetched=pdf_date,
                images=article.get("diagrams", []),
            )
            db.add(entry)
            db.commit()
            count += 1
        print(f"  CA: Stored {count} academy entries in CuratedCA with priority=high")
    finally:
        db.close()

    return count, articles


# ── Curated CA Pipeline (Editors' Cut) ──────────────────────────────────────


def _issue_id_from_title(title: str) -> str:
    """Generate a stable issue_id from a title for 48h rolling thread grouping."""
    slug = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')[:60]
    return f"{hashlib.md5(slug.encode()).hexdigest()[:12]}"


def update_trend_metrics_cache(db_ca_session, topic_tag: str, increment_source: str):
    """Maintain topic density scores in TrendMetrics cache table."""
    metric = db_ca_session.query(TrendMetrics).filter(TrendMetrics.topic_tag == topic_tag).first()
    if not metric:
        metric = TrendMetrics(topic_tag=topic_tag, live_feed_frequency=0, academy_pdf_frequency=0)
        db_ca_session.add(metric)
    if increment_source == "live_feed":
        metric.live_feed_frequency += 1
    elif increment_source == "academy_pdf":
        metric.academy_pdf_frequency += 1
    metric.computed_density_score = (metric.live_feed_frequency * 0.4) + (metric.academy_pdf_frequency * 0.6)
    metric.last_calibrated = datetime.utcnow()
    db_ca_session.commit()


LAST_FETCH_PATH = DATA_DIR / "ca_last_fetch.txt"
OFFICIAL_SOURCES = {"pib"}


def _read_last_fetch() -> str | None:
    if LAST_FETCH_PATH.exists():
        try:
            return LAST_FETCH_PATH.read_text().strip()
        except Exception:
            pass
    return None


def _write_last_fetch():
    LAST_FETCH_PATH.write_text(datetime.utcnow().isoformat())


def _download_and_extract(entry: dict):
    """Download full text + capture image for one article. Mutates entry in-place."""
    image_url = None
    full_text = entry.get("summary", "")
    try:
        import newspaper
        article = newspaper.Article(entry["link"])
        article.download()
        article.parse()
        full_text = article.text
        all_imgs = {article.top_image} | article.images if article.top_image else article.images
        if all_imgs:
            image_url = _pick_best_image(entry["title"], all_imgs)
    except Exception:
        pass
    entry["full_text"] = full_text
    entry["image_url"] = image_url


def _store_curated_entry(db: Session, entry: dict, parsed: dict, matched_via: str):
    """Create and commit a CuratedCA row from entry + parsed data."""
    matched_topic = entry.get("_llm_matched_topic", parsed.get("subject", "GS"))
    curated = CuratedCA(
        issue_id=_issue_id_from_title(entry["title"]),
        title=parsed.get("title", entry["title"]),
        source_url=entry["link"],
        source=entry["source"],
        full_text=entry.get("full_text", ""),
        summary=parsed.get("summary", ""),
        category=parsed.get("category", "General"),
        gs_linkage=matched_topic,
        tags=json.dumps(parsed.get("tags", [])),
        supporting_arguments=json.dumps(parsed.get("supporting_arguments", [])),
        counter_arguments=json.dumps(parsed.get("counter_arguments", [])),
        way_forward=json.dumps(parsed.get("way_forward", [])),
        prelims_high_yield_facts=json.dumps(parsed.get("key_facts", [])),
        matched_via=matched_via,
        matched_micro_topic=matched_topic,
        vector_match_score=entry.get("_llm_score", 0) / 100.0,
        is_academy_verified=False,
        is_supplemental=(entry["source"] in OFFICIAL_SOURCES),
        priority=("high" if entry.get("_llm_score", 50) >= 67 else "low" if entry.get("_llm_score", 50) < 34 else "medium"),
        image_url=entry.get("image_url"),
        date_of_event=parsed.get("date_of_event"),
        newspaper_name=entry["source"],
        date_fetched=str(date.today()),
    )
    db.add(curated)
    db.commit()
    db.refresh(curated)
    # Download image locally
    if entry.get("image_url"):
        local_path = _download_image(entry["image_url"], curated.id)
        if local_path:
            curated.image_url = f"/images/ca/{curated.id}"
            db.commit()
    update_trend_metrics_cache(db, parsed.get("subject", "GS"), "live_feed")


def curated_fetch_and_store():
    """Curated CA pipeline: date-filter -> split PIB/PRS -> LLM gate -> batch parse.

    - PIB/PRS articles bypass the LLM gate (always relevant, few/day).
    - Other sources go through the gate (1 call, broad filter -> top 100).
    - Enriched parse in batches of 10 via Gemini 3.1 Flash Lite.
    """
    db = SessionLocalCA()
    try:
        last_fetch = _read_last_fetch()
        print(f"  Curated CA: Last fetch at {last_fetch or 'never'}", flush=True)

        all_entries = []
        for source_name, rss_url in RSS_FEEDS.items():
            try:
                entries = _fetch_rss(rss_url)
                for e in entries:
                    e["source"] = source_name
                all_entries.extend(entries)
            except Exception as exc:
                print(f"  Curated CA fetch failed for {source_name}: {exc}", flush=True)

        all_entries = _dedup(all_entries)
        if not all_entries:
            print("  Curated CA: No articles after dedup", flush=True)
            return

        # Date filter — keep articles from same day or later (ignore time-of-day)
        if last_fetch:
            before = len(all_entries)
            last_fetch_date = datetime.fromisoformat(last_fetch).date()
            all_entries = [
                e for e in all_entries
                if not e.get("published_parsed") or e["published_parsed"].date() >= last_fetch_date
            ]
            print(f"  Curated CA: Date filter {before} -> {len(all_entries)} (since {last_fetch_date})", flush=True)
            if not all_entries:
                print("  Curated CA: No new articles since last fetch", flush=True)
                return

        # Remove already-stored URLs
        existing_urls = {
            row[0] for row in db.query(CuratedCA.source_url).all()
        }
        all_entries = [e for e in all_entries if e["link"] not in existing_urls]
        if not all_entries:
            print("  Curated CA: All articles already stored", flush=True)
            _write_last_fetch()
            return

        # Split: PIB/PRS bypass gate, others go through gate
        official = [e for e in all_entries if e["source"] in OFFICIAL_SOURCES]
        others = [e for e in all_entries if e["source"] not in OFFICIAL_SOURCES]
        print(f"  Curated CA: {len(official)} official (PIB/PRS), {len(others)} others", flush=True)

        # Track all entries that need storing
        to_store = []

        # Track PIB/PRS separately for frontend filtering
        for e in official:
            e["is_official"] = True
        for e in others:
            e["is_official"] = False

        # --- Track A: PIB/PRS -> bypass gate, download + parse directly ---
        if official:
            print(f"  Curated CA: Processing {len(official)} official articles", flush=True)
            for e in official:
                _download_and_extract(e)
                e["_llm_score"] = 80  # default high score for official sources
                e["_llm_matched_topic"] = e.get("_llm_matched_topic", "General")
            to_store.extend(official)

        # --- Track B: Other sources -> LLM gate -> top 100 -> download + parse ---
        if others:
            from ca_summary import load_ca_summary
            ca_summary = load_ca_summary()
            from ca_llm_gate import llm_quality_gate
            top_entries = llm_quality_gate(others, ca_summary)
            print(f"  Curated CA: LLM gate passed {len(top_entries)}/{len(others)}", flush=True)

            for e in top_entries:
                _download_and_extract(e)
            to_store.extend(top_entries)

        if not to_store:
            print("  Curated CA: Nothing to store", flush=True)
            _write_last_fetch()
            return

        # Second filter: keep only top high-yield articles (local, no API call)
        HIGH_YIELD_CAP = 20
        MAX_PER_SUBJECT = 5
        scored = sorted(
            [e for e in to_store if e.get("_llm_score", 0) > 0],
            key=lambda e: e["_llm_score"],
            reverse=True,
        )
        subject_count = {}
        filtered = []
        for e in scored:
            subject = e.get("_llm_gs_linkage", "GS-III")
            if subject_count.get(subject, 0) >= MAX_PER_SUBJECT:
                continue
            if len(filtered) >= HIGH_YIELD_CAP:
                break
            filtered.append(e)
            subject_count[subject] = subject_count.get(subject, 0) + 1
        # Always include official PIB articles (they have score=80 but bypass gate)
        official_included = [e for e in to_store if e.get("is_official") and e not in filtered]
        to_store = filtered + official_included
        print(f"  Curated CA: Second filter kept {len(to_store)} high-yield articles ({HIGH_YIELD_CAP} cap, {MAX_PER_SUBJECT}/subject)", flush=True)

        # Batch enriched parse (up to 10 per call)
        parsed_by_url = _batch_parse_articles(to_store)

        stored_count = 0
        for entry in to_store:
            parsed = parsed_by_url.get(entry["link"])
            if not parsed:
                continue
            try:
                _store_curated_entry(db, entry, parsed, "official" if entry.get("is_official") else "llm_gate")
                stored_count += 1
                time.sleep(0.3)
            except Exception as exc:
                print(f"  Curated CA: Store failed for {entry['link'][:60]}: {exc}", flush=True)
                db.rollback()

        print(f"  Curated CA: Stored {stored_count} articles", flush=True)
        _write_last_fetch()

    except Exception as exc:
        print(f"  Curated CA pipeline failed: {exc}", flush=True)
    finally:
        db.close()
