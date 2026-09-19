"""Ashby public job board poller.

API: https://api.ashbyhq.com/posting-api/job-board/{slug}
No auth required for public boards.
"""

import logging
import re
from datetime import datetime, timedelta, date
from html import unescape

import requests
from bs4 import BeautifulSoup

from ..models import JobPosting

log = logging.getLogger(__name__)

BASE = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def fetch(company_name: str, slug: str, lookback_days: int) -> list[JobPosting]:
    url = BASE.format(slug=slug)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        log.warning("Ashby %s: HTTP %s. Slug may be wrong.", company_name, e.response.status_code)
        return []
    except Exception as e:
        log.warning("Ashby %s: %s", company_name, e)
        return []

    cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
    jobs = []
    for item in data.get("jobs", []):
        published = _parse_date(item.get("publishedAt"))
        if published and published < cutoff:
            continue
        # Include secondary locations so a posting that lists your city as a
        # second office still passes the location check.
        locations = [item.get("location", "") or ""] + [
            (s or {}).get("location", "") for s in item.get("secondaryLocations") or []
        ]
        location = "; ".join(dict.fromkeys(loc for loc in locations if loc))
        description = _strip_html(item.get("descriptionHtml", ""))
        jobs.append(JobPosting(
            title=item.get("title", "").strip(),
            company=company_name,
            source="Ashby",
            url=item.get("jobUrl", ""),
            job_id=item.get("id", ""),
            location=location,
            remote_type=_infer_remote_type(
                location, description, item.get("isRemote", False), item.get("workplaceType")),
            salary_range=_extract_salary(item.get("compensationTierSummary"), description),
            description=description[:8000],
            posted_date=published,
        ))
    log.info("Ashby %s: %d postings within lookback", company_name, len(jobs))
    return jobs


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = BeautifulSoup(unescape(html), "html.parser").get_text(separator=" ")
    return " ".join(text.split())


def _infer_remote_type(location: str, description: str, is_remote_flag: bool,
                       workplace_type: str | None = None) -> str:
    # workplaceType is the most reliable signal. Some boards (OpenAI, Notion)
    # set isRemote=True on roles whose workplaceType is Hybrid in one city,
    # so isRemote is only trusted when workplaceType is missing.
    wt = (workplace_type or "").strip().lower()
    if wt == "remote":
        return "Remote"
    if wt == "hybrid":
        return "Hybrid"
    if wt in ("onsite", "on-site", "on site"):
        return "Onsite"
    if is_remote_flag:
        return "Remote"
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


def _extract_salary(structured, description: str) -> str:
    if structured and isinstance(structured, str) and "$" in structured:
        return structured
    m = SALARY_PATTERN.search(description or "")
    if m:
        return f"${m.group(1)} - ${m.group(2)}"
    return "N/A"
