"""SmartRecruiters public postings poller.

API:
  List:    https://api.smartrecruiters.com/v1/companies/{slug}/postings
  Details: https://api.smartrecruiters.com/v1/companies/{slug}/postings/{posting_id}

No auth required for the public Posting API.

The list endpoint does NOT include job descriptions, only metadata. To support
the two-tier skill filter, we make a follow-up details call for each posting
that's within the lookback window. This adds API calls but keeps SmartRecruiters
jobs comparable to Greenhouse/Lever/Ashby in terms of filterability.

For a typical company with 5-20 new postings per day, this means ~5-20 extra
HTTP calls per company per run. SmartRecruiters allows this without rate
limiting under normal usage.
"""

import logging
import re
from datetime import datetime, timedelta, date
from html import unescape

import requests
from bs4 import BeautifulSoup

from ..models import JobPosting

log = logging.getLogger(__name__)

LIST_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
DETAILS_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings/{posting_id}"
PAGE_SIZE = 100  # SmartRecruiters' maximum


def fetch(company_name: str, slug: str, lookback_days: int) -> list[JobPosting]:
    """Fetch jobs from SmartRecruiters for one company.

    Returns empty list on failure. Errors are logged but don't crash the pipeline.
    """
    postings = _fetch_all_postings(company_name, slug)
    if not postings:
        return []

    cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
    recent = []
    for p in postings:
        released = _parse_date(p.get("releasedDate"))
        if released is None or released >= cutoff:
            # If we can't parse the date, include it to be safe; let downstream dedup handle it
            recent.append(p)

    jobs = []
    for p in recent:
        details = _fetch_details(slug, p.get("id"))
        loc_obj = p.get("location") or {}
        location = _format_location(loc_obj)
        description = _extract_description(details) if details else ""
        posting_url = (details or {}).get("postingUrl") or _fallback_url(slug, p.get("id"))
        jobs.append(JobPosting(
            title=(p.get("name") or "").strip(),
            company=company_name,
            source="SmartRecruiters",
            url=posting_url,
            job_id=str(p.get("id", "")),
            location=location,
            remote_type=_infer_remote_type(loc_obj, location, description),
            salary_range=_extract_salary(description),
            description=description[:8000],
            posted_date=_parse_date(p.get("releasedDate")),
        ))

    log.info("SmartRecruiters %s: %d postings within lookback", company_name, len(jobs))
    return jobs


def _fetch_all_postings(company_name: str, slug: str) -> list[dict]:
    """Paginate through all postings for a company. Returns empty list on failure."""
    all_postings = []
    offset = 0
    while True:
        url = LIST_URL.format(slug=slug)
        try:
            resp = requests.get(url, params={"limit": PAGE_SIZE, "offset": offset}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as e:
            log.warning(
                "SmartRecruiters %s: HTTP %s. Slug may be wrong.",
                company_name, e.response.status_code,
            )
            return []
        except Exception as e:
            log.warning("SmartRecruiters %s: %s", company_name, e)
            return []

        content = data.get("content", []) or []
        all_postings.extend(content)

        total = data.get("totalFound", 0)
        offset += PAGE_SIZE
        if offset >= total or not content:
            break

        # Safety: don't paginate forever on a misbehaving response
        if offset > 5000:
            log.warning(
                "SmartRecruiters %s: stopping pagination after 5000 postings", company_name
            )
            break

    return all_postings


def _fetch_details(slug: str, posting_id) -> dict | None:
    """Fetch full details for one posting. Returns None on failure (silent)."""
    if not posting_id:
        return None
    url = DETAILS_URL.format(slug=slug, posting_id=posting_id)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        # SmartRecruiters format: 2024-01-15T12:34:56.493Z
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def _format_location(loc: dict) -> str:
    """Build a comma-separated location string from the structured location object.

    SmartRecruiters location keys: country (2-letter code), region, city, remote, hybrid.
    Pipeline's location parser handles "City, Region, Country" cleanly.
    """
    if not loc:
        return ""
    parts = [loc.get("city", ""), loc.get("region", ""), loc.get("country", "")]
    formatted = ", ".join(p for p in parts if p)
    # Annotate with remote/hybrid signal in parentheses so downstream parser picks it up
    if loc.get("remote") is True and "Remote" not in formatted:
        formatted = (formatted + " (Remote)").strip()
    elif loc.get("hybrid") is True and "Hybrid" not in formatted:
        formatted = (formatted + " (Hybrid)").strip()
    return formatted


def _infer_remote_type(loc_obj: dict, location_str: str, description: str) -> str:
    """SmartRecruiters provides structured remote/hybrid booleans, prefer those."""
    if loc_obj.get("remote") is True:
        return "Remote"
    if loc_obj.get("hybrid") is True:
        return "Hybrid"
    # Remote is read from the location string only. Descriptions often say
    # "remote-friendly" or "we have remote teams" in boilerplate, which used to
    # tag onsite roles (e.g. San Francisco, Toronto) as Remote and let them
    # past the location filter. Hybrid can still come from the description,
    # since hybrid and onsite are treated the same by the filter.
    loc = (location_str or "").lower()
    if "hybrid" in loc:
        return "Hybrid"
    if "remote" in loc:
        return "Remote"
    if "hybrid" in (description or "").lower():
        return "Hybrid"
    if location_str:
        return "Onsite"
    return ""


def _extract_description(details: dict) -> str:
    """Pull description text from the nested jobAd structure.

    SmartRecruiters splits the job ad into sections (jobDescription, qualifications,
    additionalInformation, companyDescription). We concatenate them all so the skill
    filter has the full text to search against.
    """
    if not details:
        return ""
    sections = (details.get("jobAd") or {}).get("sections") or {}
    parts = []
    for section_name in (
        "jobDescription",
        "qualifications",
        "additionalInformation",
        "companyDescription",
    ):
        section = sections.get(section_name)
        if isinstance(section, dict):
            text = section.get("text", "") or ""
            if text:
                parts.append(_strip_html(text))
    return " ".join(parts)


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
    match = SALARY_PATTERN.search(description)
    if match:
        return f"${match.group(1)} - ${match.group(2)}"
    return "N/A"


def _fallback_url(slug: str, posting_id) -> str:
    """Public-facing URL if details endpoint didn't return one."""
    if not posting_id:
        return f"https://jobs.smartrecruiters.com/{slug}/"
    return f"https://jobs.smartrecruiters.com/{slug}/{posting_id}"
