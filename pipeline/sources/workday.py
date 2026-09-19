"""Workday public job board poller.

API (undocumented but public, used by every myworkdayjobs.com careers site):
  POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
       body {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "..."}
  GET  https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}{externalPath}

Workday boards are large (Target and Abbott list 2,000+ jobs) and search
results come back by relevance, not date. So instead of pulling the whole
board, this runs a handful of targeted searches per company
(config.WORKDAY_SEARCH_TERMS), keeps only postings inside the lookback window,
and fetches detail pages only for titles that land in a target track.
"""

import logging
import re
from datetime import date, datetime, timedelta
from html import unescape

import requests
from bs4 import BeautifulSoup

from ..models import JobPosting

log = logging.getLogger(__name__)

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (curious_squid job pipeline)",
}
PAGE_SIZE = 20


def fetch(company_name: str, board: str, lookback_days: int,
          search_terms: list[str], max_pages: int = 2) -> list[JobPosting]:
    """Fetch recent, title-matching jobs for one Workday board.

    `board` is "tenant|wdN|site", e.g. "capitalone|12|Capital_One".
    Returns an empty list on any failure so one bad board never stops the run.
    """
    # Imported here to avoid a circular import (filter imports models too).
    from ..filter import classify_title

    try:
        tenant, wd, site = board.split("|")
    except ValueError:
        log.warning("Workday %s: bad board spec %r (want tenant|wdN|site)", company_name, board)
        return []
    base = f"https://{tenant}.wd{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"

    # 1. Search: collect recent postings whose titles land in a target track.
    candidates: dict[str, dict] = {}
    errors = 0
    for term in search_terms:
        for page in range(max_pages):
            body = {"appliedFacets": {}, "limit": PAGE_SIZE,
                    "offset": page * PAGE_SIZE, "searchText": term}
            try:
                resp = requests.post(base + "/jobs", json=body, headers=HEADERS, timeout=20)
                resp.raise_for_status()
                postings = resp.json().get("jobPostings", []) or []
            except Exception as e:
                errors += 1
                log.debug("Workday %s search %r failed: %s", company_name, term, e)
                break
            for p in postings:
                path = p.get("externalPath")
                if not path or path in candidates:
                    continue
                age = _posted_days_ago(p.get("postedOn", ""))
                if age is None or age > lookback_days:
                    continue
                if not classify_title(p.get("title", "")):
                    continue
                candidates[path] = p
            if len(postings) < PAGE_SIZE:
                break

    if errors and not candidates and errors >= len(search_terms):
        log.warning("Workday %s: every search failed. Board spec may be wrong.", company_name)
        return []

    # 2. Detail: full description, all locations, remote type, real start date.
    jobs = []
    for path, p in candidates.items():
        try:
            resp = requests.get(base + path, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            info = resp.json().get("jobPostingInfo", {})
        except Exception as e:
            log.debug("Workday %s detail %s failed: %s", company_name, path, e)
            continue
        location = _join_locations(info)
        description = _strip_html(info.get("jobDescription", ""))
        jobs.append(JobPosting(
            title=(info.get("title") or p.get("title", "")).strip(),
            company=company_name,
            source="Workday",
            url=info.get("externalUrl") or f"https://{tenant}.wd{wd}.myworkdayjobs.com/{site}{path}",
            job_id=info.get("jobReqId") or info.get("jobPostingId", ""),
            location=location,
            remote_type=_infer_remote_type(info.get("remoteType"), location),
            salary_range=_extract_salary(description),
            description=description[:8000],
            posted_date=_parse_date(info.get("startDate")),
        ))
    log.info("Workday %s: %d matching postings within lookback", company_name, len(jobs))
    return jobs


POSTED_PATTERN = re.compile(r"posted\s+(\d+)\+?\s+days?\s+ago", re.IGNORECASE)


def _posted_days_ago(posted_on: str) -> int | None:
    """Turn Workday's "Posted Today" / "Posted Yesterday" / "Posted 3 Days Ago"
    / "Posted 30+ Days Ago" into a day count. None if unrecognized."""
    s = (posted_on or "").strip().lower()
    if "today" in s:
        return 0
    if "yesterday" in s:
        return 1
    m = POSTED_PATTERN.search(s)
    if m:
        return int(m.group(1))
    return None


def _join_locations(info: dict) -> str:
    """Primary + additional locations, plus the country when it isn't the US,
    so location.py can tag non-US roles (e.g. "Penang, Malaysia")."""
    locs = [info.get("location") or ""] + list(info.get("additionalLocations") or [])
    joined = "; ".join(dict.fromkeys(loc for loc in locs if loc))
    country = ((info.get("country") or {}).get("descriptor") or "").strip()
    if country and "united states" not in country.lower() and country.lower() not in joined.lower():
        joined = f"{joined}; {country}" if joined else country
    return joined


def _infer_remote_type(remote_type: str | None, location: str) -> str:
    """Prefer Workday's structured remoteType; fall back to the location text."""
    rt = (remote_type or "").lower()
    if "remote" in rt:
        return "Remote"
    if "hybrid" in rt:
        return "Hybrid"
    if rt:
        return "Onsite"
    loc = (location or "").lower()
    if "hybrid" in loc:
        return "Hybrid"
    if "remote" in loc:
        return "Remote"
    return "Onsite" if location else ""


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:10]).date()
    except ValueError:
        return None


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = BeautifulSoup(unescape(html), "html.parser").get_text(separator=" ")
    return " ".join(text.split())


SALARY_PATTERN = re.compile(
    r"\$\s*(\d{2,3}(?:,\d{3})?(?:\.\d{2})?)"
    r"\s*(?:-|to|–)\s*"
    r"\$?\s*(\d{2,3}(?:,\d{3})?(?:\.\d{2})?)"
)


def _extract_salary(description: str) -> str:
    if not description:
        return "N/A"
    m = SALARY_PATTERN.search(description)
    return f"${m.group(1)} - ${m.group(2)}" if m else "N/A"
