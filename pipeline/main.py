"""
Pipeline orchestrator.

Run this as the entrypoint. Reads everything from environment variables
so the same code works locally and in GitHub Actions.

Required environment variables:
  AIRTABLE_API_KEY          - your Airtable personal access token (starts with "pat...")
  AIRTABLE_BASE_ID          - your Airtable base ID (starts with "app...")
  GMAIL_ADDRESS             - your gmail address
  GMAIL_APP_PASSWORD        - 16-char app password from myaccount.google.com/apppasswords

There is no AI/LLM scoring step. Jobs are written to the Pipeline table
with Status="New" for manual review in Airtable.
"""

import logging
import os
import sys

from . import config
from .airtable_client import AirtableClient
from .preflight import run_airtable_preflight
from .filter import pre_filter
from .sources import ashby, gmail_parser, greenhouse, lever, smartrecruiters


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"FATAL: missing required env var {name}", file=sys.stderr)
        sys.exit(2)
    return value


def gather_postings(gmail_address: str, gmail_password: str) -> list:
    """Pull from every source and return a combined list of JobPostings."""
    all_jobs = []

    # Gmail (LinkedIn + Indeed alerts) via IMAP
    try:
        gmail_jobs = gmail_parser.fetch_all(
            email_address=gmail_address,
            app_password=gmail_password,
            linkedin_query=config.GMAIL_LINKEDIN_QUERY,
            indeed_query=config.GMAIL_INDEED_QUERY,
            lookback_days=config.LOOKBACK_DAYS,
        )
        all_jobs.extend(gmail_jobs)
    except Exception as e:
        logging.error("Gmail source failed: %s", e)

    # ATS pollers
    poller = {
        "greenhouse": greenhouse.fetch,
        "lever": lever.fetch,
        "ashby": ashby.fetch,
        "smartrecruiters": smartrecruiters.fetch,
    }
    for company_name, ats, slug in config.TARGET_COMPANIES:
        if ats not in poller:
            logging.warning("Unknown ATS %s for %s, skipping", ats, company_name)
            continue
        try:
            jobs = poller[ats](company_name, slug, config.LOOKBACK_DAYS)
            all_jobs.extend(jobs)
        except Exception as e:
            logging.error("%s %s failed: %s", ats, company_name, e)

    logging.info("Source totals: %d postings collected", len(all_jobs))
    return all_jobs


def dedupe_within_batch(jobs: list) -> list:
    """Drop in-batch duplicates by URL, then by (company, title)."""
    seen_urls = set()
    seen_pairs = set()
    out = []
    for job in jobs:
        url_key = (job.url or "").strip().lower()
        if url_key and url_key in seen_urls:
            continue
        from .models import _normalize
        pair = (_normalize(job.company), _normalize(job.title))
        if all(pair) and pair in seen_pairs:
            continue
        seen_urls.add(url_key)
        if all(pair):
            seen_pairs.add(pair)
        out.append(job)
    logging.info("In-batch dedup: %d -> %d", len(jobs), len(out))
    return out


def main() -> int:
    configure_logging()

    airtable_key = require_env("AIRTABLE_API_KEY")
    base_id = require_env("AIRTABLE_BASE_ID")
    gmail_address = require_env("GMAIL_ADDRESS")
    gmail_password = require_env("GMAIL_APP_PASSWORD")

    # Validate the Airtable base, tables and fields up front. Fails with a
    # plain-language message instead of a raw traceback if setup is wrong.
    run_airtable_preflight(airtable_key, base_id)

    # 1. Gather
    raw = gather_postings(gmail_address, gmail_password)

    # 2. In-batch dedup
    deduped = dedupe_within_batch(raw)

    # 3. Cross-run dedup against existing Pipeline + Job Applications
    airtable = AirtableClient(api_key=airtable_key, base_id=base_id)
    existing = airtable.get_existing_dedup_keys()
    fresh = [j for j in deduped if not airtable.is_duplicate(j, existing)]
    logging.info("Cross-run dedup: %d -> %d", len(deduped), len(fresh))

    # 4. Pre-filter
    filtered = pre_filter(fresh)

    # 5. Write (no scoring step; review manually in Airtable)
    written = airtable.write_pipeline_rows(filtered)

    logging.info("Run complete. Wrote %d new Pipeline rows.", written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
