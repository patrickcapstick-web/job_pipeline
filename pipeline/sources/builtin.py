"""Built In job board fetcher (builtin.com and its city sites, e.g.
builtinchicago.org, builtinnyc.com, builtinaustin.com).

Built In has no public API, but its pages carry schema.org JSON-LD:
  - /jobs?search=<term>&daysSinceUpdated=<n>  -> an ItemList of job URLs
  - /job/<slug>/<id>                          -> a JobPosting with company,
                                                 full description, location,
                                                 remote flag, date and salary
robots.txt allows /jobs and /job/ (it disallows /search, which isn't used).

To stay light on their servers: a fixed list of search terms, at most
BUILTIN_MAX_PAGES pages each, detail pages only for titles that land in a
target track, and a pause between every request.
"""

import html
import json
import logging
import re
import time
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from ..models import JobPosting

log = logging.getLogger(__name__)

DEFAULT_SITE = "https://builtin.com"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128 Safari/537.36"),
    "Accept": "text/html",
}
LD_JSON = re.compile(r'<script type="application/ld(?:&#x2B;|\+)json">(.*?)</script>', re.S)
PAGE_SIZE = 25
PAUSE_SECONDS = 1.0


def fetch_all(search_terms: list[str], lookback_days: int, max_pages: int = 2,
              site: str = DEFAULT_SITE) -> list[JobPosting]:
    """Search a Built In site and return title-matching postings.

    Never raises: a blocked or changed site logs a warning and returns [].
    """
    from ..filter import classify_title  # avoid circular import

    session = requests.Session()
    session.headers.update(HEADERS)
    days = max(1, lookback_days)

    # 1. Search pages -> candidate URLs with a target-track title.
    candidates: dict[str, str] = {}
    pages_ok = 0
    for term in search_terms:
        for page in range(1, max_pages + 1):
            params = {"search": term, "daysSinceUpdated": days}
            if page > 1:
                params["page"] = page
            items = _search_page(session, site.rstrip("/"), params)
            time.sleep(PAUSE_SECONDS)
            if items is None:
                break
            pages_ok += 1
            for name, url in items:
                if url not in candidates and classify_title(name):
                    candidates[url] = name
            if len(items) < PAGE_SIZE:
                break

    if pages_ok == 0:
        log.warning("Built In: no search page could be read (blocked or page format changed)")
        return []

    # 2. Detail pages -> JobPostings.
    jobs = []
    for url in candidates:
        posting = _job_posting(session, url)
        time.sleep(PAUSE_SECONDS)
        if posting:
            job = _to_job(posting, url)
            if job:
                jobs.append(job)
    log.info("Built In: %d matching postings (%d search pages read)", len(jobs), pages_ok)
    return jobs


def _ld_blocks(page_html: str) -> list[dict]:
    """Every JSON-LD object on a page, with @graph containers flattened."""
    out = []
    for raw in LD_JSON.findall(page_html):
        try:
            data = json.loads(html.unescape(raw))
        except json.JSONDecodeError:
            continue
        out.extend(data.get("@graph", [data]) if isinstance(data, dict) else [])
    return out


def _search_page(session, site, params) -> list[tuple[str, str]] | None:
    """(title, url) pairs from one search page, or None if it can't be read."""
    try:
        resp = session.get(site + "/jobs", params=params, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        log.debug("Built In search %s failed: %s", params, e)
        return None
    for block in _ld_blocks(resp.text):
        if block.get("@type") == "ItemList":
            return [(i.get("name", ""), i.get("url", ""))
                    for i in block.get("itemListElement", []) if i.get("url")]
    return []


def _job_posting(session, url) -> dict | None:
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        log.debug("Built In detail %s failed: %s", url, e)
        return None
    for block in _ld_blocks(resp.text):
        if block.get("@type") == "JobPosting":
            return block
    return None


def _to_job(p: dict, url: str) -> JobPosting | None:
    company = ((p.get("hiringOrganization") or {}).get("name") or "").strip()
    title = (p.get("title") or "").strip()
    if not (company and title):
        return None
    remote = (p.get("jobLocationType") or "").upper() == "TELECOMMUTE"
    location = _location(p.get("jobLocation"), remote)
    description = BeautifulSoup(p.get("description") or "", "html.parser").get_text(" ")
    return JobPosting(
        title=title,
        company=company,
        source="Built In",
        url=url,
        job_id=url.rstrip("/").rsplit("/", 1)[-1],
        location=location,
        remote_type="Remote" if remote else ("Hybrid" if "hybrid" in location.lower() else "Onsite"),
        salary_range=_salary(p.get("baseSalary")),
        description=" ".join(description.split())[:8000],
        posted_date=_parse_date(p.get("datePosted")),
    )


def _location(job_location, remote: bool) -> str:
    """"Chicago, IL"-style string from one or more JSON-LD Place objects."""
    places = job_location if isinstance(job_location, list) else [job_location or {}]
    parts = []
    for place in places:
        addr = (place or {}).get("address") or {}
        bits = [addr.get("addressLocality"), addr.get("addressRegion")]
        country = addr.get("addressCountry")
        if country and country not in ("USA", "US", "United States"):
            bits.append(country)
        text = ", ".join(b for b in bits if b)
        if text:
            parts.append(text)
    loc = "; ".join(dict.fromkeys(parts))
    if remote:
        loc = f"Remote, United States; {loc}" if loc else "Remote, United States"
    return loc


def _salary(base_salary) -> str:
    value = (base_salary or {}).get("value") or {}
    lo, hi = value.get("minValue"), value.get("maxValue")
    if lo and hi and (value.get("unitText") or "YEAR").upper() == "YEAR":
        return f"${int(lo):,} - ${int(hi):,}"
    return "N/A"


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:10]).date()
    except ValueError:
        return None
