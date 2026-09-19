"""Lever public postings poller.

API: https://api.lever.co/v0/postings/{slug}?mode=json
No auth required for public boards.
"""

import logging
from datetime import datetime, timedelta, date

import requests

from ..models import JobPosting

log = logging.getLogger(__name__)

BASE = "https://api.lever.co/v0/postings/{slug}?mode=json"


def fetch(company_name: str, slug: str, lookback_days: int) -> list[JobPosting]:
    url = BASE.format(slug=slug)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        log.warning("Lever %s: HTTP %s. Slug may be wrong.", company_name, e.response.status_code)
        return []
    except Exception as e:
        log.warning("Lever %s: %s", company_name, e)
        return []

    cutoff_ms = (datetime.utcnow() - timedelta(days=lookback_days)).timestamp() * 1000
    jobs = []
    for item in data:
        created = item.get("createdAt", 0)
        if created and created < cutoff_ms:
            continue
        categories = item.get("categories", {}) or {}
        location = categories.get("location", "")
        commitment = categories.get("commitment", "")
        description = item.get("descriptionPlain", "") or ""
        jobs.append(JobPosting(
            title=item.get("text", "").strip(),
            company=company_name,
            source="Lever",
            url=item.get("hostedUrl", ""),
            job_id=item.get("id", ""),
            location=location,
            remote_type=_infer_remote_type(location, description),
            salary_range=_extract_salary(item.get("salaryRange"), description),
            description=description[:8000],
            posted_date=_ms_to_date(created),
        ))
    log.info("Lever %s: %d postings within lookback", company_name, len(jobs))
    return jobs


def _ms_to_date(ms: int) -> date | None:
    if not ms:
        return None
    try:
        return datetime.utcfromtimestamp(ms / 1000).date()
    except Exception:
        return None


def _infer_remote_type(location: str, description: str) -> str:
    # Remote is read from the location string only. Descriptions often say
    # "remote-friendly" or "we have remote teams" in boilerplate, which used to
    # tag onsite roles (e.g. San Francisco, Toronto) as Remote and let them
    # past the location filter. Hybrid can still come from the description,
    # since hybrid and onsite are treated the same by the filter.
    loc = (location or "").lower()
    if "hybrid" in loc:
        return "Hybrid"
    if "remote" in loc:
        return "Remote"
    if "hybrid" in (description or "").lower():
        return "Hybrid"
    if location:
        return "Onsite"
    return ""


def _extract_salary(structured, description: str) -> str:
    if structured and isinstance(structured, dict):
        mn = structured.get("min")
        mx = structured.get("max")
        if mn and mx:
            return f"${int(mn):,} - ${int(mx):,}"
    # Fallback to regex parsing of description
    import re
    pat = re.compile(
        r"\$\s*(\d{2,3}(?:,\d{3})?(?:\.\d{2})?)"
        r"\s*(?:-|to|–)\s*"
        r"\$?\s*(\d{2,3}(?:,\d{3})?(?:\.\d{2})?)"
    )
    m = pat.search(description or "")
    if m:
        return f"${m.group(1)} - ${m.group(2)}"
    return "N/A"
