"""Pre-filter logic. Cheap checks that drop obvious misses before writing to Airtable.

Every job that passes also gets a Match Score (0-100) so you can sort the
Pipeline table with the best fits on top. See score_job() below.
"""

import logging
import re

from .models import JobPosting
from . import config

log = logging.getLogger(__name__)

# Email alert sources carry no job description, so skill checks can't run on them.
EMAIL_SOURCES = ("LinkedIn Email", "Indeed Email")


def _word_match(text_low: str, phrase_low: str) -> bool:
    """True if `phrase_low` occurs in `text_low` bounded by non-alphanumeric
    edges (or string ends), tolerating a simple trailing plural "s". Both args
    must already be lowercase.

    Short tokens ("mode", "vp", "sas programming") match only as standalone
    words/phrases, not inside larger words ("model", "Kansas", "PostgreSQL").
    Internal punctuation ("a/b test", "self-serve", "power bi") is preserved
    via re.escape. The optional trailing "s" lets plurals ("ETLs", "LLMs")
    match without reopening substring collisions.
    """
    pattern = r"(?:^|[^a-z0-9])" + re.escape(phrase_low) + r"s?(?:[^a-z0-9]|$)"
    return bool(re.search(pattern, text_low))


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    """Return the subset of `keywords` found as whole words/phrases in `text`."""
    if not text:
        return []
    low = text.lower()
    return [kw for kw in keywords if _word_match(low, kw)]


# -----------------------------------------------------------------------------
# Title
# -----------------------------------------------------------------------------

def classify_title(title: str) -> bool:
    """True if the title matches TARGET_TITLES and no EXCLUDE_TITLE_TERMS.
    (Used by the Workday and Built In sources to decide which postings are
    worth opening.)"""
    low = (title or "").lower()
    if not any(_word_match(low, target) for target in config.TARGET_TITLES):
        return False
    if any(_word_match(low, term) for term in config.EXCLUDE_TITLE_TERMS):
        return False
    return True


def passes_title_filter(title: str) -> bool:
    return classify_title(title)


# -----------------------------------------------------------------------------
# Location
# -----------------------------------------------------------------------------

def is_remote_role(job: JobPosting) -> bool:
    """True if the role is remote.

    remote_type comes from the job-board sources, which read it from the
    location field and the board's own remote/hybrid setting only, never from
    the description. (Descriptions often say "remote-friendly" in boilerplate,
    which used to mark onsite jobs in other cities as remote.) The title and
    location text are also checked because LinkedIn alerts put "(Remote)" in
    the location.
    """
    if job.remote_type and job.remote_type.strip().lower() == "remote":
        return True
    haystack = f"{job.title or ''} {job.location or ''}".lower()
    return any(_word_match(haystack, kw) for kw in config.REMOTE_KEYWORDS)


def is_us_eligible(job: JobPosting) -> bool:
    """True unless the location points outside the US ("Remote Spain",
    "Canada - Remote", "Bangalore"). A bare "Remote" is kept."""
    if job.country and job.country != "United States":
        return False
    if job.region and job.region not in ("US", "Global"):
        return False
    loc = (job.location or "").lower()
    if any(_word_match(loc, city) for city in config.NON_US_CITY_TERMS):
        return False
    return True


def matches_allowed_city(job: JobPosting) -> bool:
    """True if the job's location contains one of ALLOWED_ONSITE_LOCATIONS."""
    loc = (job.location or "").lower()
    return any(city in loc for city in config.ALLOWED_ONSITE_LOCATIONS)


def passes_location_filter(job: JobPosting) -> bool:
    """Keep onsite/hybrid roles in one of your cities, or remote roles
    (US-based only when REMOTE_US_ONLY is True)."""
    if matches_allowed_city(job):
        return True
    if not is_remote_role(job):
        return False
    return is_us_eligible(job) if config.REMOTE_US_ONLY else True


# -----------------------------------------------------------------------------
# Skills and score
# -----------------------------------------------------------------------------

def count_core_stack_matches(text: str) -> list[str]:
    """Tier 1: tools and methods that signal stack alignment with your experience."""
    return _match_keywords(text, config.CORE_STACK_KEYWORDS)


def count_broad_skill_matches(text: str) -> list[str]:
    """Tier 2: broader signals that this is a data-analyst-shaped role in a relevant domain."""
    return _match_keywords(text, config.BROAD_SKILL_KEYWORDS)


def score_job(core: list[str], broad: list[str]) -> int:
    """Match Score, 0-100: SCORE_BASE plus capped points per skill hit.
    More of your tools and signals in the description = higher score."""
    per_core, max_core = config.SCORE_CORE_POINTS
    per_broad, max_broad = config.SCORE_BROAD_POINTS
    score = config.SCORE_BASE + min(len(core) * per_core, max_core) \
        + min(len(broad) * per_broad, max_broad)
    return max(0, min(score, 100))


# -----------------------------------------------------------------------------
# Orchestration
# -----------------------------------------------------------------------------

def pre_filter(jobs: list[JobPosting]) -> list[JobPosting]:
    """Run company, title, location and two-tier skill checks; score survivors.

    LinkedIn and Indeed alert emails carry no description, so they pass on
    title + location alone and get SCORE_BASE as their Match Score. Your
    LinkedIn alert settings are the de facto pre-filter for that source.

    A role with a description must pass:
      - At least MIN_CORE_STACK_MATCHES Tier 1 hits (tools you use)
      - At least MIN_BROAD_SKILL_MATCHES Tier 2 hits (broader signals)

    Survivors come back sorted by Match Score, highest first.
    """
    survivors = []
    drops = {"company": 0, "title": 0, "location": 0, "core": 0, "broad": 0}

    for job in jobs:
        company_low = (job.company or "").lower()
        if any(_word_match(company_low, c.lower()) for c in config.EXCLUDE_COMPANIES):
            drops["company"] += 1
            continue

        if not passes_title_filter(job.title):
            drops["title"] += 1
            continue

        if not passes_location_filter(job):
            drops["location"] += 1
            continue

        if job.source in EMAIL_SOURCES:
            job.matched_skills = []
            job.match_score = config.SCORE_BASE
            survivors.append(job)
            continue

        haystack = f"{job.title} {job.description}"
        core_matched = count_core_stack_matches(haystack)
        broad_matched = count_broad_skill_matches(haystack)
        job.matched_skills = core_matched + broad_matched

        if len(core_matched) < config.MIN_CORE_STACK_MATCHES:
            drops["core"] += 1
            continue
        if len(broad_matched) < config.MIN_BROAD_SKILL_MATCHES:
            drops["broad"] += 1
            continue

        job.match_score = score_job(core_matched, broad_matched)
        survivors.append(job)

    survivors.sort(key=lambda j: j.match_score, reverse=True)
    log.info(
        "Pre-filter: %d in, %d out (dropped %d on title, %d on location, "
        "%d on core stack, %d on broad skills, %d excluded company)",
        len(jobs), len(survivors), drops["title"], drops["location"],
        drops["core"], drops["broad"], drops["company"],
    )
    return survivors
