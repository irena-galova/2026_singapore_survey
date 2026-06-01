#!/usr/bin/env python3
"""Generate a self-contained, Kestria-branded feedback dashboard from the
SurveyMonkey CSV export of the 2026 Kestria Global Conference in Singapore.

Run:  python3 build.py
Output: index.html (self-contained static page, ready for Vercel)
"""

import csv
import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSV_PATH = HERE.parent / "CSV" / "2026 Kestria Global Conference in Singapore.csv"
OUT_PATH = HERE / "index.html"

# Total participants invited to the conference (denominator for the response rate).
TOTAL_PARTICIPANTS = 54

NUM_RE = re.compile(r"^\d+(\.\d+)?$")
SCALE_SUFFIX_RE = re.compile(r"\s*-\s*\d+\s*$")

# Comments to omit under Q1 (venue & dinner restaurants) - non-substantive notes.
Q1_VENUE_TITLE = "Conference venue & dinner restaurants"
Q1_SKIP_NAMES = {"Intan Jalaludin", "Ryan Berrecloth", "Guy Brew"}

# Wrong apostrophe characters (acute accent / backtick) used instead of '.
APOSTROPHE_FIXES = [
    ("doesn\u00b4t", "doesn't"),
    ("don\u00b4t", "don't"),
    ("it`s", "it's"),
]

# Obvious spelling / missing-space typos. Meaning is preserved.
TYPO_FIXES = [
    (r"\bintroductary\b", "introductory"),
    (r"\bsinc\b", "since"),
    (r"\bSuccesion\b", "Succession"),
    (r"\bdiscusssed\b", "discussed"),
    (r"\babut\b", "about"),
    (r"\bshouldnt\b", "shouldn't"),
    (r"\bdont\b", "don't"),
    (r"\bcanidates\b", "candidates"),
    (r"\bImprovewebsite\b", "Improve website"),
    (r"\bprosising\b", "promising"),
    (r"\bofexecutive\b", "of executive"),
    (r"\bkonw\b", "know"),
    (r"\bproporsition\b", "proposition"),
    (r"\brecuding\b", "reducing"),
    (r"\bleaverage\b", "leverage"),
    (r"\bbrigde\b", "bridge"),
    (r"\bassigments\b", "assignments"),
    (r"\bPractive\b", "Practice"),
    (r"\bspeach\b", "speech"),
    (r"\bconfrerence\b", "conference"),
    (r"\bapart of\b", "a part of"),
    (r"the test of the days", "the rest of the days"),
    (r"people we're eating the food", "people were eating the food"),
    (r"broader your perspective", "broaden your perspective"),
]


def fix_name(name: str) -> str:
    """Normalize name casing: Wu Nine Jee, Raj Kumar, Pedro Antão, etc."""
    def cap(tok):
        if not tok:
            return tok
        # All-caps word (e.g. WU, NINE, JEE) → title case
        if len(tok) >= 2 and tok.isupper() and tok.isalpha():
            return tok[0].upper() + tok[1:].lower()
        # Leading lowercase (e.g. raj) → capitalize first letter only
        if tok[0].islower():
            return tok[0].upper() + tok[1:]
        return tok
    return " ".join(cap(t) for t in name.split())


def fix_text(s: str) -> str:
    """Correct obvious typos in respondent comments without changing meaning."""
    for wrong, right in APOSTROPHE_FIXES:
        s = s.replace(wrong, right)
    for pat, rep in TYPO_FIXES:
        s = re.sub(pat, rep, s)
    return s


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip trailing punctuation for matching."""
    t = fix_text(text).lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t.rstrip(".!?,;:- ")


# Responses with no substantive content — omitted from the dashboard.
LOW_VALUE_EXACT = {
    "-",
    "na",
    "n/a",
    "not yet",
    "not applicable",
    "no current thoughts",
    "no direct proposal",
    "none i can think of now",
    "none, as per usual",
    "none as per usual",
    "same",
    "same as above",
    "see above",
    "as above",
    "the same as above",
    "nothing in my mind at the moment",
    "nothing in mind at the moment",
    "i don't know",
    "i dont know",
}

LOW_VALUE_PREFIX = (
    "guess i covered that",
    "need to figure",
    "still brainstorming",
    "nothing in my mind",
    "nothing in mind",
    "no thoughts",
    "no comment",
    "cannot answer",
    "can't answer",
)


def is_low_value(text: str) -> bool:
    """True when a response adds no meaningful insight."""
    n = _normalize(text)
    if not n:
        return True
    if n in LOW_VALUE_EXACT:
        return True
    if any(n.startswith(p) for p in LOW_VALUE_PREFIX):
        return True
    return False

# Display order for rating sections (venue & dinners moved to third).
RATING_ORDER = [
    "Conference sessions",
    "Dragon boat teambuilding activity",
    "Conference venue & dinner restaurants",
]

# AI-generated summaries for rating sections. Clearly labelled in the UI.
RATING_SUMMARIES = {
    "Conference venue & dinner restaurants": (
        "Andaz scored highly (9.2); dinners lower (6–7). Main feedback: venues too "
        "loud for conversation, menus too similar over three nights — quieter settings "
        "and more international options requested."
    ),
    "Dragon boat teambuilding activity": (
        "The dragon boat teambuilding was one of the most enjoyed parts of the "
        "conference (8.8), repeatedly described as great fun and a highlight for team "
        "spirit. The main suggestions were practical: warn participants in advance that "
        "they will get soaked, and reconsider the timing given the humid weather and an "
        "already packed schedule."
    ),
    "Conference sessions": (
        "Conference sessions were rated strongly overall (8.4). The highest-rated were "
        "Dr. Ayesha Khanna's AI keynote (9.3) and 'The Authenticity Advantage' (9.2), "
        "with the AI content cited again and again as the most valuable and thought-"
        "provoking. The lowest-rated were the sponsor and tool sessions - Ezekia (7.3), "
        "Hogan (7.4) and Proactive Agility (7.5) - which some felt were repetitive year "
        "over year."
    ),
}

TEXT_TOP_INSIGHTS = {
    "What are the main takeaways from the Kestria Global Conference in Singapore that you plan to implement in your practice?": [
        "Integrate AI tools into the search process and day-to-day workflows.",
        "Shift the value proposition from 'finding' talent to leadership advisory.",
        "Strengthen cross-border collaboration with Kestria partners.",
        "Use the Kestria brand and global network more actively with clients.",
        "Deepen authentic, trust-based relationships with clients and candidates.",
    ],
    "What is one cross-border business development initiative that you can implement in your local firm within the next 30 days?": [
        "Map local clients with global headquarters or international operations.",
        "Identify portfolio clients also served by global partners and initiate joint outreach.",
        "Build a target list and schedule intro calls with relevant Kestria colleagues.",
        "Explore specific regional or sector opportunities with partners abroad.",
        "Restart a newsletter or direct outreach to stay top of mind with key contacts.",
    ],
    "What is one cross-border business development initiative that you think your Practice Group can implement in your local firm within the next 30-60 days?": [
        "Dedicate regular PG meeting time to cross-border opportunities and market intelligence.",
        "Share case studies, best practices and insights across the global network.",
        "Map clients in the PG with cross-border hiring or expansion needs.",
        "Coordinate joint business development on shared or multinational accounts.",
        "Review cross-border pipeline progress on a quarterly basis.",
    ],
    "What is your one takeaway to boost your local and global = GloCal marketing and positioning?": [
        "Position the firm as a local advisor with global reach through the Kestria brand.",
        "Increase use of Kestria content — newsletters, blogs, white papers and social media.",
        "Improve website SEO and reshare Kestria posts more consistently.",
        "Promote Kestria global capabilities in every client and prospect conversation.",
        "Use Kestria templates and market insights to strengthen local positioning.",
    ],
}

TEXT_SUMMARIES = {
    "What should we do differently next time?": (
        "The most repeated request is to improve the dinners and venues (quieter, less "
        "repetitive, more international). Many also want the business development and "
        "Practice Group sessions rethought, as they feel repetitive year to year, and "
        "several found the sponsor-led presentations less engaging. The client event and "
        "the high-energy, authentic format were highlighted as successes worth keeping."
    ),
    "What topics would you like us to cover in future Kestria Virtual Academy events (including our online webinars)?": (
        "AI dominates the wish list - especially practical AI tools and workflows for "
        "business development and recruitment. Respondents also want more on future-"
        "proof leadership, how-to guidance for initiating cross-border business, market "
        "and economic insights, and the evolution of executive search toward strategic "
        "advisory."
    ),
}


# --- Comment formatting -----------------------------------------------------
# Characters that count as already-terminal punctuation (so we don't add a dot).
TERMINAL_PUNCT = ".!?:;)]}\"'\u2019\u201d\u2026"
NUM_ITEM_RE = re.compile(r"(?:(?<=\s)|^)\d+[.)]\s+")
DASH_SPLIT_RE = re.compile(r"\s*[-\u2022]\s+")


def _cap_first(s: str) -> str:
    """Capitalize the first alphabetic character (leave numbers/bullets alone)."""
    for i, ch in enumerate(s):
        if ch.isalpha():
            return s[:i] + ch.upper() + s[i + 1:]
        if ch.isdigit():
            break
    return s


def _as_sentence(s: str) -> str:
    """Make an obvious sentence proper: capital first letter, trailing period."""
    s = s.strip()
    if not s:
        return s
    s = _cap_first(s)
    if any(c.isalpha() for c in s) and s[-1] not in TERMINAL_PUNCT:
        s += "."
    return s


def parse_comment(text: str):
    """Classify a comment as a sentence or a bullet list.

    Returns ('text', sentence) or ('list', lead_in_or_None, [items]).
    Bullet lists are detected for numbered ('1. .. 2. ..') or dash-prefixed
    content; a single in-line dash (e.g. 'too loud - no chance') stays a sentence.
    """
    t = re.sub(r"\s+", " ", text).strip()

    # Numbered list: '1. ... 2. ...'
    if len(NUM_ITEM_RE.findall(t)) >= 2:
        parts = NUM_ITEM_RE.split(t)
        lead = parts[0].strip()
        items = [p.strip() for p in parts[1:] if p.strip()]
        if len(items) >= 2:
            return ("list", _as_sentence(lead) if lead else None,
                    [_as_sentence(x) for x in items])

    # Dash bullets: starts with '- ' or uses ' - ' as 2+ separators.
    starts_dash = bool(re.match(r"^\s*[-\u2022]\s+", t))
    separators = len(re.findall(r"\s-\s+", t))
    if starts_dash or separators >= 2:
        parts = [p.strip() for p in DASH_SPLIT_RE.split(t) if p.strip()]
        lead = None
        if not starts_dash and parts and parts[0].rstrip().endswith(":"):
            lead = _as_sentence(parts[0])
            parts = parts[1:]
        if len(parts) >= 2:
            return ("list", lead, [_as_sentence(x) for x in parts])

    return ("text", _as_sentence(t))


def item_base(label: str) -> str:
    """Strip a trailing ' - N' scale suffix from a sub-column label."""
    return SCALE_SUFFIX_RE.sub("", label).strip()


def load():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header_q, header_item = rows[0], rows[1]
    data = [r for r in rows[2:] if any(c.strip() for c in r)]

    # Forward-fill the (sparse) question header row.
    q = ""
    qfill = []
    for c in header_q:
        if c.strip():
            q = c.strip()
        qfill.append(q)

    return header_q, header_item, qfill, data


def build_rating_questions(header_item, qfill, data):
    """Return ordered rating questions, each with items {name, avg, n} and comments."""
    n = len(header_item)

    # Group contiguous columns that belong to the same rating item (share the
    # forward-filled question text, the same base label, and a ' - N' suffix).
    groups = []  # (question_text, item_base, [col indices])
    i = 0
    while i < n:
        lbl = header_item[i].strip()
        is_scale = bool(SCALE_SUFFIX_RE.search(lbl))
        if is_scale and qfill[i].lower().startswith("how would you rate"):
            q = qfill[i]
            base = item_base(lbl)
            cols = []
            while (
                i < n
                and qfill[i] == q
                and SCALE_SUFFIX_RE.search(header_item[i].strip())
                and item_base(header_item[i].strip()) == base
            ):
                cols.append(i)
                i += 1
            groups.append((q, base, cols))
        else:
            i += 1

    # Dedicated free-text comment columns ("Additional comments") per question.
    comment_cols = {}  # question_text -> col index
    for idx, lbl in enumerate(header_item):
        if lbl.strip() == "Additional comments":
            comment_cols[qfill[idx]] = idx

    name_col = next(i for i, c in enumerate(header_item) if c.strip() == "Name")

    # Pretty titles for the rating questions.
    def question_title(qtext):
        low = qtext.lower()
        if "venue and dinner" in low:
            return "Conference venue & dinner restaurants"
        if "dragon boat" in low:
            return "Dragon boat teambuilding activity"
        if "conference sessions" in low:
            return "Conference sessions"
        return qtext

    questions = []
    seen = []
    for qtext, base, cols in groups:
        if qtext not in seen:
            seen.append(qtext)
            questions.append({
                "title": question_title(qtext),
                "items": [],
                "comments": [],
                "_qtext": qtext,
            })
        bucket = next(x for x in questions if x["_qtext"] == qtext)

        scores = []
        for r in data:
            vals = [r[c].strip() for c in cols if c < len(r) and r[c].strip()]
            nums = [float(v) for v in vals if NUM_RE.match(v)]
            if nums:
                scores.append(max(nums))
        avg = round(sum(scores) / len(scores), 1) if scores else None
        # The dragon-boat single item has an empty base label.
        item_name = base if base else "Overall rating"
        bucket["items"].append({"name": item_name, "avg": avg, "n": len(scores)})
        bucket.setdefault("_pool", []).extend(scores)

    # Overall (pooled) average across every individual rating in the question.
    for bucket in questions:
        pool = bucket.pop("_pool", [])
        bucket["overall"] = round(sum(pool) / len(pool), 1) if pool else None

    # Attach comments.
    for bucket in questions:
        ccol = comment_cols.get(bucket["_qtext"])
        if ccol is None:
            continue
        for r in data:
            text = r[ccol].strip() if ccol < len(r) else ""
            if not text:
                continue
            raw_name = r[name_col].strip() if name_col < len(r) else ""
            if bucket["title"] == Q1_VENUE_TITLE and raw_name in Q1_SKIP_NAMES:
                continue
            fixed = fix_text(text)
            if is_low_value(fixed):
                continue
            bucket["comments"].append({"name": fix_name(raw_name), "text": fixed})

    for b in questions:
        b.pop("_qtext", None)
    return questions


def build_text_questions(header_q, header_item, qfill, data):
    """Q4-Q9 open-ended answers, attributed by respondent name."""
    name_col = next(i for i, c in enumerate(header_item) if c.strip() == "Name")
    open_cols = [i for i, c in enumerate(header_item) if c.strip() == "Open-Ended Response"]

    # The question text for each open-ended column lives in header_q at that column.
    results = []
    for col in open_cols:
        title = header_q[col].strip()
        answers = []
        for r in data:
            text = r[col].strip() if col < len(r) else ""
            if text:
                fixed = fix_text(text)
                if is_low_value(fixed):
                    continue
                name = r[name_col].strip() if name_col < len(r) else ""
                answers.append({"name": fix_name(name), "text": fixed})
        results.append({"title": title, "answers": answers})
    return results


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_ai_summary(text) -> str:
    if not text:
        return ""
    return f"""
        <div class="ai-summary">
          <div class="ai-summary-head"><span class="ai-badge">AI</span> Summary</div>
          <p class="ai-summary-body">{esc(text)}</p>
        </div>"""


def render_top_insights(items) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{esc(it)}</li>" for it in items)
    return f"""
        <div class="ai-summary">
          <div class="ai-summary-head"><span class="ai-badge">AI</span> Top insights</div>
          <ul class="ai-insights">{lis}</ul>
        </div>"""


def render_comment(c) -> str:
    name = esc(c["name"] or "Anonymous")
    parsed = parse_comment(c["text"])
    if parsed[0] == "list":
        _, lead, items = parsed
        body = f'<span class="comment-text">{esc(lead)}</span>' if lead else ""
        body += '<ul class="bullets">' + "".join(
            f"<li>{esc(it)}</li>" for it in items) + "</ul>"
    else:
        body = f'<span class="comment-text">{esc(parsed[1])}</span>'
    return f'<li class="comment"><span class="comment-name">{name}:</span> {body}</li>'


def render_item(it) -> str:
    avg = it["avg"]
    avg_str = f"{avg:.1f}" if avg is not None else "-"
    pct = (avg / 10 * 100) if avg is not None else 0
    return f"""
        <div class="item">
          <div class="item-head">
            <span class="item-name">{esc(it['name'])}</span>
            <span class="item-score"><span class="score-num">{avg_str}</span><span class="score-max">/10</span></span>
          </div>
          <div class="bar"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>
        </div>"""


def render_overall_box(label, val) -> str:
    val_str = f"{val:.1f}" if val is not None else "-"
    solo = "" if label else " overall-box--solo"
    label_html = f'<span class="overall-label">{esc(label)}</span>' if label else ""
    return f"""
        <div class="overall-box{solo}">{label_html}
          <span class="overall-score"><span class="score-num">{val_str}</span><span class="score-max">/10</span></span>
        </div>"""


def render_comments_block(comments) -> str:
    if not comments:
        return ""
    lis = "\n".join(render_comment(c) for c in comments)
    return f"""
        <div class="comments">
          <h3 class="comments-title">Comments</h3>
          <ul class="comment-list">{lis}</ul>
        </div>"""


def render_rating_question(q) -> str:
    title = q["title"]
    body = [render_ai_summary(RATING_SUMMARIES.get(title))]

    if title == "Dragon boat teambuilding activity":
        body.append(render_overall_box("Team building activity rating", q.get("overall")))
    elif title == "Conference sessions":
        body.append(render_overall_box("Overall conference rating", q.get("overall")))
        body.append('<div class="items">' + "".join(render_item(it) for it in q["items"]) + "</div>")
    else:
        body.append('<div class="items">' + "".join(render_item(it) for it in q["items"]) + "</div>")

    body.append(render_comments_block(q["comments"]))
    return f"""
      <section class="card">
        <h2 class="card-title">{esc(title)}</h2>{''.join(body)}
      </section>"""


def render_text_question(q) -> str:
    title = q["title"].strip()
    if title in TEXT_TOP_INSIGHTS:
        summary = render_top_insights(TEXT_TOP_INSIGHTS[title])
    else:
        summary = render_ai_summary(TEXT_SUMMARIES.get(title))
    if not q["answers"]:
        lis = '<li class="comment comment-empty">No responses.</li>'
    else:
        lis = "\n".join(render_comment(a) for a in q["answers"])
    return f"""
      <section class="card">
        <h2 class="card-title">{esc(q['title'])}</h2>{summary}
        <ul class="comment-list">{lis}</ul>
      </section>"""


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kestria Global Conference in Singapore - Feedback</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:ital,wght@0,400;0,600;0,700;0,800;1,700&family=Noto+Sans:ital,wght@0,400;0,600;0,700;1,400&family=Oswald:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --blue: #0057b0;
    --dark-blue: #0c2340;
    --gold: #c0865e;
    --white: #ffffff;
    --ink: #1a2230;
    --muted: #5b6675;
    --line: #e6e9ef;
    --bg: #f5f6f8;
    --card: #ffffff;
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: "Noto Sans", Arial, sans-serif;
    font-size: 16px;
    line-height: 1.6;
  }
  .wrap { max-width: 920px; margin: 0 auto; padding: 20px 20px 40px; }

  .hero-banner {
    background: var(--dark-blue);
    color: var(--white);
    padding: 36px 20px 32px;
  }
  .hero-banner-inner {
    max-width: 920px;
    margin: 0 auto;
  }
  .hero-title {
    font-family: "Montserrat", sans-serif;
    font-weight: 700;
    font-size: clamp(26px, 4.5vw, 36px);
    line-height: 1.2;
    margin: 0 0 10px;
    color: var(--white);
  }
  .hero-sub {
    font-family: "Noto Sans", Arial, sans-serif;
    font-size: 17px;
    margin: 0;
    opacity: 0.92;
  }
  .section-banner {
    margin-top: 0;
    padding: 28px 20px 24px;
  }
  .section-banner .hero-title {
    font-size: clamp(22px, 3.5vw, 28px);
    margin: 0;
  }
  .hero-photo {
    display: block;
    width: 100%;
    height: auto;
    margin: 0;
  }

  /* Cards */
  .card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 24px 26px;
    margin: 0 0 20px;
    box-shadow: 0 1px 2px rgba(12,35,64,0.04);
  }
  .card-title {
    font-family: "Montserrat", sans-serif;
    font-weight: 700;
    font-size: 19px;
    color: var(--dark-blue);
    margin: 0 0 18px;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--line);
  }

  /* AI summary */
  .ai-summary {
    background: #faf4ee;
    border: 1px solid #ecd9c8;
    border-left: 4px solid var(--gold);
    border-radius: 10px;
    padding: 14px 18px 16px;
    margin: 0 0 22px;
  }
  .ai-summary-head {
    font-family: "Montserrat", sans-serif;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 12px;
    color: var(--gold);
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }
  .ai-badge {
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.04em;
    background: var(--gold);
    color: #fff;
    padding: 2px 7px;
    border-radius: 5px;
  }
  .ai-summary-body {
    margin: 0;
    color: #6a4f3a;
    font-size: 14.5px;
    line-height: 1.55;
  }
  .ai-insights {
    margin: 0;
    padding-left: 20px;
    color: #6a4f3a;
    font-size: 14.5px;
    line-height: 1.55;
  }
  .ai-insights li { margin: 5px 0; }

  /* Overall / single score box */
  .overall-box {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    background: var(--dark-blue);
    color: #fff;
    border-radius: 12px;
    padding: 16px 24px;
    margin: 0 0 20px;
  }
  .overall-box--solo { justify-content: center; gap: 0; }
  .overall-label {
    font-family: "Montserrat", sans-serif;
    font-weight: 700;
    font-size: 16px;
    letter-spacing: 0.01em;
  }
  .overall-box .score-num { font-size: 42px; line-height: 1; }
  .overall-box .score-max { color: rgba(255,255,255,0.65); font-size: 17px; }

  .item { margin: 0 0 16px; }
  .item:last-child { margin-bottom: 0; }
  .item-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 16px;
  }
  .item-name { font-weight: 600; color: var(--ink); }
  .item-score { white-space: nowrap; }
  .score-num {
    font-family: "Oswald", "Montserrat", sans-serif;
    font-weight: 700;
    font-size: 28px;
    color: var(--gold);
  }
  .score-max { color: var(--muted); font-size: 14px; margin-left: 2px; }
  .bar {
    height: 8px;
    background: #eef1f5;
    border-radius: 6px;
    margin-top: 8px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--blue), #2f7fce);
    border-radius: 6px;
  }

  .comments { margin-top: 22px; padding-top: 18px; border-top: 1px dashed var(--line); }
  .comments-title {
    font-family: "Montserrat", sans-serif;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 12px;
    color: var(--muted);
    margin: 0 0 12px;
  }
  .comment-list { list-style: none; margin: 0; padding: 0; }
  .comment {
    padding: 12px 0;
    border-bottom: 1px solid var(--line);
  }
  .comment:last-child { border-bottom: none; }
  .comment-name { font-weight: 700; color: var(--blue); }
  .comment-text { color: var(--ink); }
  .comment-empty { color: var(--muted); font-style: italic; }
  .bullets { margin: 6px 0 0; padding-left: 22px; }
  .bullets li { margin: 3px 0; color: var(--ink); }

  footer {
    text-align: center;
    color: var(--muted);
    font-size: 13px;
    margin: 48px 0 0;
    padding-bottom: 24px;
  }

  @media (max-width: 560px) {
    .card { padding: 20px 18px; }
  }

  @media print {
    body { background: #fff; }
    .card { box-shadow: none; break-inside: avoid; }
  }
</style>
</head>
<body>
  <header class="hero-banner">
    <div class="hero-banner-inner">
      <h1 class="hero-title">Kestria Global Conference in Singapore</h1>
      <p class="hero-sub">Post-conference feedback (__RESP__ of __TOTAL__ participants shared their feedback)</p>
    </div>
  </header>

  <div class="hero-banner section-banner">
    <div class="hero-banner-inner">
      <h2 class="hero-title">Ratings</h2>
    </div>
  </div>
  <div class="wrap">
    __RATINGS__
  </div>

  <div class="hero-banner section-banner">
    <div class="hero-banner-inner">
      <h2 class="hero-title">In their own words</h2>
    </div>
  </div>
  <div class="wrap">
    __TEXTS__

    <footer>Kestria &middot; 2026 Global Conference, Singapore</footer>
  </div>

  <img class="hero-photo" src="conference-photo.png" alt="Kestria Global Conference 2026, Singapore — group photo">
</body>
</html>
"""


def order_rating_questions(questions):
    by_title = {q["title"]: q for q in questions}
    return [by_title[t] for t in RATING_ORDER if t in by_title]


def main():
    header_q, header_item, qfill, data = load()
    n_resp = len(data)
    pct = round(n_resp / TOTAL_PARTICIPANTS * 100)

    rating_questions = order_rating_questions(
        build_rating_questions(header_item, qfill, data)
    )
    text_questions = build_text_questions(header_q, header_item, qfill, data)

    ratings_html = "\n".join(render_rating_question(q) for q in rating_questions)
    texts_html = "\n".join(render_text_question(q) for q in text_questions)

    page = (
        PAGE.replace("__RESP__", str(n_resp))
        .replace("__TOTAL__", str(TOTAL_PARTICIPANTS))
        .replace("__RATINGS__", ratings_html)
        .replace("__TEXTS__", texts_html)
    )

    OUT_PATH.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"Respondents: {n_resp} ({pct}% of {TOTAL_PARTICIPANTS})")
    print(f"Rating questions: {len(rating_questions)} | Text questions: {len(text_questions)}")
    for q in rating_questions:
        print(f"  - {q['title']}: {len(q['items'])} item(s), {len(q['comments'])} comment(s)")


if __name__ == "__main__":
    main()
