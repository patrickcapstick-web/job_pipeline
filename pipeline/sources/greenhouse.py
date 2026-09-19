"""Greenhouse public job board poller.

API: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
No auth required for public boards.
"""

import logging
from datetime import datetime, timedelta, date
from html import unescape
import re

import requests
from bs4 import BeautifulSoup

from ..models import JobPosting

log = logging.getLogger(__name__)

BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def fetch(company_name: str, slug: str, lookback_days: int) -> list[JobPosting]:
    """Fetch jobs from Greenhouse for one company. Returns empty list on failure."""
    url = BASE.format(slug=slug) + "?content=true"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        log.warning("Greenhouse %s: HTTP %s. Slug may be wrong.", company_name, e.response.status_code)
        return []
    except Exception as e:
        log.warning("Greenhouse %s: %s", company_name, e)
        return []

    cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
    jobs = []
    for item in data.get("jobs", []):
        updated = _parse_date(item.get("updated_at"))
        if updated and updated < cutoff:
            continue
        description = _strip_html(item.get("content", ""))
        location = (item.get("location") or {}).get("name", "")
        jobs.append(JobPosting(
            title=item.get("title", "").strip(),
            company=company_name,
            source="Greenhouse",
            url=item.get("absolute_url", ""),
            job_id=str(item.get("id", "")),
            location=location,
            remote_type=_infer_remote_type(location, description),
            salary_range=_extract_salary(description),
            description=description,
            posted_date=updated,
        ))
    log.info("Greenhouse %s: %d postings within lookback", company_name, len(jobs))
    return jobs


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        # Greenhouse format: 2024-01-15T12:34:56-05:00
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = BeautifulSoup(unescape(html), "html.parser").get_text(separator=" ")
    return " ".join(text.split())


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


SALARY_PATTERN = re.compile(
    r"\$\s*(\d{2,3}(?:,\d{3})?(?:\.\d{2})?)"
    r"\s*(?:-|to|–)\s*"
    r"\$?\s*(\d{2,3}(?:,\d{3})?(?:\.\d{2})?)"
)


def _extract_salary(description: str) -> str:
    """Best-effort salary range extraction from description text."""
    if not description:
        return "N/A"
    match = SALARY_PATTERN.search(description)
    if match:
        return f"${match.group(1)} - ${match.group(2)}"
    return "N/A"
