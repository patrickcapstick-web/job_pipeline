"""
Airtable preflight checks.

Runs before the main pipeline and turns the most common first-time setup
mistakes into plain-language messages, instead of letting a raw Airtable
HTTPError traceback surface in the logs.

Covered:
  - access token not connected to the base (Airtable returns 404 "Not Found")
  - wrong or mistyped base ID
  - invalid token or missing scopes (401 / 403)
  - a required table missing or misnamed
  - a required field missing or misnamed (Airtable returns 422
    "Unknown field name" partway through a run)

On any problem this raises SystemExit with a readable message, which stops the
run cleanly without a stack trace.
"""

import logging

from pyairtable import Api

log = logging.getLogger(__name__)

# Tables the pipeline expects, spelled exactly.
REQUIRED_TABLES = ("Pipeline", "Companies", "Job Applications")

# Fields the pipeline reads or writes on each table, spelled exactly. These
# mirror section 2 of SETUP.md. A missing field here is what triggers a 422
# "Unknown field name" error partway through a run.
REQUIRED_FIELDS = {
    "Pipeline": [
        "Job Title", "Company", "Job ID", "Location", "Remote Type",
        "Source", "URL", "Salary Range", "Posted Date", "Found Date",
        "Status", "Matched Skills", "Region", "Country", "State", "City",
    ],
    "Companies": ["Company Name"],
    "Job Applications": ["Job Title", "Company"],
}

# Optional Pipeline fields. Written only when they exist, so an older base
# without them keeps working. See SETUP.md section 2.5.
OPTIONAL_PIPELINE_FIELDS = ("Match Score",)

_BAR = "=" * 70


def _banner(lines):
    return "\n".join(["", _BAR, "AIRTABLE SETUP PROBLEM", _BAR, *lines, _BAR])


def _connection_error_message(err):
    status = None
    resp = getattr(err, "response", None)
    if resp is not None:
        status = getattr(resp, "status_code", None)

    if status in (401, 403):
        return _banner([
            f"Airtable rejected your access token (HTTP {status}).",
            "",
            "Check two things:",
            "",
            "1. Scopes. Open https://airtable.com/create/tokens, click your",
            "   token, and under 'Scopes' confirm all three are present:",
            "      - data.records:read",
            "      - data.records:write",
            "      - schema.bases:read",
            "",
            "2. The token value. The AIRTABLE_API_KEY secret in GitHub must be",
            "   the whole token (it starts with 'pat'). If unsure, make a new",
            "   token and paste it in again.",
            "",
            "GitHub secrets: your repo > Settings > Secrets and variables >",
            "Actions. Full walkthrough is in SETUP.md (Troubleshooting).",
        ])

    return _banner([
        "Airtable could not find your base, so it returned 'Not Found'.",
        "",
        "This almost always means ONE of the following. Check in order:",
        "",
        "1. Your token is not connected to this base (the usual cause).",
        "   Go to https://airtable.com/create/tokens, click your token, and",
        "   under 'Access' make sure your base is listed. If it is not, click",
        "   'Add a base', choose your base, then 'Save changes'.",
        "",
        "2. The base ID is wrong or mistyped.",
        "   Open your base in the browser. The address looks like",
        "   airtable.com/appXXXXXXXX/tbl...  The part that starts with 'app'",
        "   is the base ID. Re-copy it and update the AIRTABLE_BASE_ID secret",
        "   in GitHub (Settings > Secrets and variables > Actions).",
        "",
        "3. The token is missing the schema.bases:read scope.",
        "   On the same token page, under 'Scopes', add schema.bases:read.",
        "",
        "Step-by-step help is in SETUP.md (Troubleshooting section).",
    ])


def _missing_tables_message(missing, present):
    lines = [
        "Your base was found, but a required table is missing or has a",
        "different name. Table names are case-sensitive and must match",
        "exactly.",
        "",
    ]
    present_lower = {p.lower(): p for p in present}
    for name in missing:
        near = present_lower.get(name.lower())
        if near:
            lines.append(f"  - needs '{name}' : you have '{near}'. Rename it "
                         f"to exactly '{name}'.")
        else:
            lines.append(f"  - needs '{name}' : not found. Create a table "
                         f"named exactly '{name}'.")
    lines += [
        "",
        "Tables now in your base: " + (", ".join(sorted(present)) or "(none)"),
        "",
        "See section 2.2 of SETUP.md for creating and naming the tables.",
    ]
    return _banner(lines)


def _missing_fields_message(missing_by_table):
    lines = [
        "Your tables were found, but some required fields (columns) are",
        "missing or named differently. Field names are case-sensitive and",
        "must match exactly. This is what causes an 'Unknown field name'",
        "error partway through a run.",
        "",
    ]
    for table, info in missing_by_table.items():
        lines.append(f"Table '{table}':")
        present_lower = {p.lower(): p for p in info["present"]}
        for name in info["missing"]:
            near = present_lower.get(name.lower())
            if near:
                lines.append(f"  - needs '{name}' : you have '{near}'. Rename "
                             f"it to exactly '{name}'.")
            else:
                lines.append(f"  - needs '{name}' : not found. Add a field "
                             f"named exactly '{name}'.")
        lines.append("")
    lines += [
        "The Company field on 'Pipeline' and 'Job Applications' must be a",
        "'Link to another record' field pointing at the Companies table.",
        "",
        "See section 2.5 of SETUP.md for the full field list and types.",
    ]
    return _banner(lines)


def run_airtable_preflight(api_key, base_id):
    """Validate the base, tables and fields before the main run.

    Raises SystemExit with a readable, plain-language message on any problem,
    so the GitHub Actions log shows what to fix rather than a stack trace.
    On success, returns the set of field names on the Pipeline table, so the
    writer knows which optional fields it can fill in.
    """
    api = Api(api_key)
    try:
        schema = api.base(base_id).schema()
    except Exception as err:
        raise SystemExit(_connection_error_message(err))

    tables = {t.name: t for t in schema.tables}

    missing_tables = [name for name in REQUIRED_TABLES if name not in tables]
    if missing_tables:
        raise SystemExit(_missing_tables_message(missing_tables, set(tables)))

    missing_by_table = {}
    for table_name, expected in REQUIRED_FIELDS.items():
        present = {f.name for f in tables[table_name].fields}
        gap = [f for f in expected if f not in present]
        if gap:
            missing_by_table[table_name] = {"missing": gap, "present": present}
    if missing_by_table:
        raise SystemExit(_missing_fields_message(missing_by_table))

    log.info("Airtable preflight OK: base, tables and fields all present.")
    pipeline_fields = {f.name for f in tables["Pipeline"].fields}
    for name in OPTIONAL_PIPELINE_FIELDS:
        if name not in pipeline_fields:
            log.info("Optional Pipeline field '%s' not found, so it will be "
                     "skipped. Add it to use it (SETUP.md section 2.5).", name)
    return pipeline_fields
