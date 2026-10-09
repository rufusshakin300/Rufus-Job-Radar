import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

STATE_FILE = Path("state.json")
TIMEOUT = 25
HEADERS = {"User-Agent": "RufusJobRadar/1.0 (personal job alerts)"}

ROLE_TERMS = [
    ".net developer", "dotnet developer", "asp.net", "c# developer",
    "software engineer", "software developer", "backend developer",
    "full stack developer", "dynamics 365", "d365", "dynamics crm",
    "power platform", "dataverse", "crm developer"
]
TECH_TERMS = [
    ".net", "dotnet", "asp.net", "c#", "dynamics 365", "d365",
    "power platform", "dataverse", "dynamics crm", "crm", "sql server",
    "web api", "entity framework"
]
SENIOR_TERMS = [
    "senior", "sr.", "staff engineer", "principal", "tech lead",
    "team lead", "engineering manager", "director", "architect"
]
INDIA_TERMS = [
    "india", "hyderabad", "bengaluru", "bangalore", "remote", "anywhere",
    "worldwide", "asia", "apac"
]
PREFERRED_LOCATIONS = ["hyderabad", "bengaluru", "bangalore", "remote"]

def get_json(url, params=None):
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"Source request failed: {url}: {exc}", file=sys.stderr)
        return None

def strip_html(value):
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value or "")
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def normalize_job(title, company, location, url, description="", source="", posted=""):
    if not url or not title:
        return None
    return {
        "title": strip_html(title),
        "company": strip_html(company or "Company not listed"),
        "location": strip_html(location or "Location not listed"),
        "url": url.strip(),
        "description": strip_html(description)[:5000],
        "source": source,
        "posted": str(posted or "")
    }

def fetch_remotive():
    data = get_json("https://remotive.com/api/remote-jobs", params={"category": "software-dev", "limit": 500})
    jobs = []
    for item in (data or {}).get("jobs", []):
        job = normalize_job(
            item.get("title"), item.get("company_name"),
            item.get("candidate_required_location") or "Remote",
            item.get("url"), item.get("description"), "Remotive",
            item.get("publication_date")
        )
        if job:
            jobs.append(job)
    return jobs

def fetch_arbeitnow():
    data = get_json("https://www.arbeitnow.com/api/job-board-api")
    jobs = []
    for item in (data or {}).get("data", []):
        job = normalize_job(
            item.get("title"), item.get("company_name"),
            item.get("location"), item.get("url"),
            item.get("description"), "Arbeitnow",
            item.get("created_at")
        )
        if job:
            jobs.append(job)
    return jobs

def fetch_greenhouse():
    # Add company board slugs to greenhouse_boards.json. Official public board API.
    path = Path("greenhouse_boards.json")
    if not path.exists():
        return []
    try:
        boards = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        print("greenhouse_boards.json could not be parsed.", file=sys.stderr)
        return []
    jobs = []
    for board in boards:
        slug = board.get("slug", "").strip()
        if not slug:
            continue
        data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
        for item in (data or {}).get("jobs", []):
            location = (item.get("location") or {}).get("name", "")
            job = normalize_job(
                item.get("title"), board.get("company", slug), location,
                item.get("absolute_url"), item.get("content", ""),
                "Company career site (Greenhouse)", item.get("updated_at", "")
            )
            if job:
                jobs.append(job)
    return jobs

def fetch_lever():
    # Add company site slugs to lever_boards.json. Official public postings API.
    path = Path("lever_boards.json")
    if not path.exists():
        return []
    try:
        boards = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        print("lever_boards.json could not be parsed.", file=sys.stderr)
        return []
    jobs = []
    for board in boards:
        slug = board.get("slug", "").strip()
        if not slug:
            continue
        data = get_json(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
        for item in data if isinstance(data, list) else []:
            categories = item.get("categories") or {}
            location = categories.get("location", "")
            description = " ".join([
                item.get("descriptionPlain", ""),
                " ".join(x.get("content", "") for x in item.get("lists", []) if isinstance(x, dict))
            ])
            job = normalize_job(
                item.get("text"), board.get("company", slug), location,
                item.get("hostedUrl"), description,
                "Company career site (Lever)", item.get("createdAt", "")
            )
            if job:
                jobs.append(job)
    return jobs

def location_matches(job):
    loc = (job["location"] + " " + job["description"][:1500]).lower()
    # Global remote listings are included if they don't explicitly restrict candidates
    # to a country outside India.
    outside_restrictions = [
        "united states only", "us only", "usa only", "uk only",
        "europe only", "must be located in the united states",
        "must reside in the united states", "canada only"
    ]
    if any(term in loc for term in outside_restrictions):
        return False
    return any(term in loc for term in INDIA_TERMS) or not job["location"].strip()

def score_job(job):
    title = job["title"].lower()
    text = (title + " " + job["description"][:5000]).lower()
    if any(term in title for term in SENIOR_TERMS):
        return 0
    if not any(term in text for term in ROLE_TERMS):
        return 0
    if not any(term in text for term in TECH_TERMS):
        return 0
    if not location_matches(job):
        return 0

    score = 50
    if any(term in title for term in ["dynamics 365", "d365", "power platform", "crm developer"]):
        score += 20
    if any(term in title for term in [".net", "dotnet", "asp.net", "c#", "backend developer"]):
        score += 20
    loc = job["location"].lower()
    if any(term in loc for term in ["hyderabad", "bengaluru", "bangalore"]):
        score += 15
    if "remote" in loc or "india" in loc or "worldwide" in loc:
        score += 10
    if re.search(r"\b(1|2|3)\s*[-–to]+\s*(3|4)\s*years?\b", text) or re.search(r"\b1\+?\s*years?\b", text):
        score += 10
    if any(term in text for term in ["asp.net core", "dataverse", "power apps", "entity framework", "sql server"]):
        score += 5
    return score

def load_state():
    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")).get("sent", []))
    except Exception:
        return set()

def save_state(sent):
    STATE_FILE.write_text(json.dumps({"sent": sorted(sent)[-3000:]}, indent=2), encoding="utf-8")

def telegram_send(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as GitHub Actions secrets.")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram message limit is 4096 chars; split digests safely below that.
    for start in range(0, len(message), 3800):
        response = requests.post(
            url, json={"chat_id": chat_id, "text": message[start:start + 3800], "disable_web_page_preview": True},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API rejected message: {payload}")

def main():
    jobs = fetch_remotive() + fetch_arbeitnow() + fetch_greenhouse() + fetch_lever()
    seen_urls = set()
    unique = []
    for job in jobs:
        key = job["url"].split("?")[0].rstrip("/").lower()
        if key in seen_urls:
            continue
        seen_urls.add(key)
        score = score_job(job)
        if score > 0:
            job["score"] = score
            unique.append(job)

    unique.sort(key=lambda j: (j["score"], j["posted"]), reverse=True)
    sent_before = load_state()
    new_jobs = [j for j in unique if j["url"].split("?")[0].rstrip("/").lower() not in sent_before]
    # Send up to 15 new matches each day. Keep state even when no matches arrive.
    selected = new_jobs[:15]

    if selected:
        lines = [f"🔎 Rufus Job Radar — {len(selected)} new match(es)", "Target: .NET + D365 | Hyderabad, Bengaluru, Remote India", ""]
        for i, job in enumerate(selected, 1):
            lines.extend([
                f"{i}. {job['title']}",
                f"Company: {job['company']}",
                f"Location: {job['location'] or 'Not listed'}",
                f"Match score: {job['score']}/100 | Source: {job['source']}",
                f"Apply / view: {job['url']}",
                ""
            ])
        lines.append("Note: check the full description and eligibility before applying. Some source links lead to the job-board listing rather than the employer's application form.")
        message = "\n".join(lines)
    else:
        message = "🔎 Rufus Job Radar\nNo new matching jobs found today from the configured sources. The workflow ran successfully."

    telegram_send(message)
    sent_before.update(j["url"].split("?")[0].rstrip("/").lower() for j in selected)
    save_state(sent_before)
    print(f"Fetched {len(jobs)} listings; {len(unique)} matched filters; sent {len(selected)} new jobs.")

if __name__ == "__main__":
    main()
