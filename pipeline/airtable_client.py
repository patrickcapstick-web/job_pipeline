"""
Airtable client for the Pipeline table.

Responsibilities:
  - Fetch existing dedup keys from Pipeline AND Job Applications so the
    script never writes a row for a job that's already been seen or applied to.
  - Find or create the Company record for each new posting, then link it.
  - Write new Pipeline rows.

Uses pyairtable: https://pyairtable.readthedocs.io/
"""

import logging
from datetime import date

from pyairtable import Api

from .models import JobPosting, _normalize

log = logging.getLogger(__name__)


class AirtableClient:
    def __init__(self, api_key: str, base_id: str, pipeline_fields: set | None = None):
        # Field names present on the Pipeline table (from preflight). Used to
        # decide whether optional fields like "Match Score" can be written.
        self.pipeline_fields = pipeline_fields or set()
        self.api = Api(api_key)
        self.pipeline = self.api.table(base_id, "Pipeline")
        self.applications = self.api.table(base_id, "Job Applications")
        self.companies = self.api.table(base_id, "Companies")

    # -------------------------------------------------------------------------
    # Dedup
    # -------------------------------------------------------------------------

    def get_existing_dedup_keys(self) -> dict:
        """Return three sets that the writer checks against before inserting:
            urls               -> set of normalized URLs already in Pipeline
            source_job_ids     -> set of (source, job_id) tuples in Pipeline
            company_title_pairs -> set of (norm_company, norm_title) in Pipeline OR Job Applications
        """
        urls = set()
        source_job_ids = set()
        company_title_pairs = set()

        # Build companyId -> name map once so we can resolve linked records
        company_lookup = {
            rec["id"]: rec["fields"].get("Company Name", "")
            for rec in self.companies.all(fields=["Company Name"])
        }

        for rec in self.pipeline.all(fields=["URL", "Source", "Job ID", "Job Title", "Company"]):
            f = rec["fields"]
            url = (f.get("URL") or "").strip().lower()
            if url:
                urls.add(url)
            src = f.get("Source", "")
            jid = f.get("Job ID", "")
            if src and jid:
                source_job_ids.add((src, jid))
            company_ids = f.get("Company") or []
            company_name = company_lookup.get(company_ids[0], "") if company_ids else ""
            title = f.get("Job Title", "")
            if company_name and title:
                company_title_pairs.add((_normalize(company_name), _normalize(title)))

        # Already-applied roles should never re-surface in Pipeline either
        for rec in self.applications.all(fields=["Job Title", "Company"]):
            f = rec["fields"]
            company_ids = f.get("Company") or []
            company_name = company_lookup.get(company_ids[0], "") if company_ids else ""
            title = f.get("Job Title", "")
            if company_name and title:
                company_title_pairs.add((_normalize(company_name), _normalize(title)))

        log.info(
            "Dedup load: %d URLs, %d source/job_id pairs, %d company/title pairs",
            len(urls), len(source_job_ids), len(company_title_pairs),
        )
        return {
            "urls": urls,
            "source_job_ids": source_job_ids,
            "company_title_pairs": company_title_pairs,
        }

    def is_duplicate(self, job: JobPosting, existing: dict) -> bool:
        """Apply the three-tier dedup check."""
        url = (job.url or "").strip().lower()
        if url and url in existing["urls"]:
            return True
        if job.job_id and (job.source, job.job_id) in existing["source_job_ids"]:
            return True
        pair = (_normalize(job.company), _normalize(job.title))
        if all(pair) and pair in existing["company_title_pairs"]:
            return True
        return False

    # -------------------------------------------------------------------------
    # Company linking
    # -------------------------------------------------------------------------

    _company_cache: dict[str, str] = {}

    def get_or_create_company(self, company_name: str) -> str | None:
        """Return the Companies record ID for company_name, creating it if needed.

        Match is case-insensitive on the Company Name primary field. If the
        company name is empty, returns None and the caller should skip the link.
        """
        if not company_name:
            return None
        key = _normalize(company_name)
        if key in self._company_cache:
            return self._company_cache[key]

        # Try to find existing
        formula = f'LOWER({{Company Name}}) = "{key}"'
        matches = self.companies.all(formula=formula, fields=["Company Name"], max_records=1)
        if matches:
            rec_id = matches[0]["id"]
            self._company_cache[key] = rec_id
            return rec_id

        # Create new
        try:
            new = self.companies.create({"Company Name": company_name})
            rec_id = new["id"]
            self._company_cache[key] = rec_id
            log.info("Created Companies record for %s", company_name)
            return rec_id
        except Exception as e:
            log.warning("Could not create Companies record for %s: %s", company_name, e)
            return None

    # -------------------------------------------------------------------------
    # Write
    # -------------------------------------------------------------------------

    def write_pipeline_rows(self, jobs: list[JobPosting]) -> tuple[int, int]:
        """Write JobPostings to the Pipeline table.

        Returns (written, failed). A non-zero failed count makes the run exit
        with an error, so a broken write shows up as a red run in GitHub
        Actions instead of a green run that quietly saved nothing. (With a
        1-day lookback, a missed write is a job you never see.)
        """
        today = date.today().isoformat()
        records = []
        for job in jobs:
            company_id = self.get_or_create_company(job.company)
            fields = {
                "Job Title": job.title,
                "Job ID": job.job_id,
                "Location": job.location,
                "Source": job.source,
                "URL": job.url,
                "Salary Range": job.salary_range or "N/A",
                "Found Date": today,
                "Status": "New",
            }
            if job.remote_type:
                fields["Remote Type"] = job.remote_type
            if job.posted_date:
                fields["Posted Date"] = job.posted_date.isoformat()
            if company_id:
                fields["Company"] = [company_id]
            # Structured location fields. Only write the ones that have content
            # so we don't clobber existing values with empty strings.
            if job.city:
                fields["City"] = job.city
            if job.state:
                fields["State"] = job.state
            if job.country:
                fields["Country"] = job.country
            if job.region:
                fields["Region"] = job.region
            # Matched skills: which Tier 1 + Tier 2 keywords fired for this role.
            # Joined to a string so it works whether the Airtable field is a
            # single-line text or long-text field. Guarded like the fields above
            # so we never write an empty value. This is the main signal for
            # reviewing false positives by hand: it shows *why* a role passed.
            if job.match_score and "Match Score" in self.pipeline_fields:
                fields["Match Score"] = job.match_score
            if job.matched_skills:
                fields["Matched Skills"] = ", ".join(job.matched_skills)
            records.append({"fields": fields})

        if not records:
            return 0, 0

        # Batch in chunks of 10 (Airtable's default batch limit)
        written = 0
        failed = 0
        for i in range(0, len(records), 10):
            chunk = records[i:i + 10]
            try:
                self.pipeline.batch_create([r["fields"] for r in chunk], typecast=True)
                written += len(chunk)
            except Exception as e:
                failed += len(chunk)
                log.error("Failed to write batch starting at %d: %s", i, e)
        log.info("Wrote %d Pipeline rows (%d failed)", written, failed)
        return written, failed
