# curious_squid: an automated job-finding pipeline

This is a small, free tool that does your job searching for you. Once a day it:

1. **Reads** new postings from your LinkedIn and Indeed alert emails, plus the public careers pages of companies you choose (via Greenhouse, Lever, Ashby, SmartRecruiters and, optionally, Workday), plus the Built In job site if you turn it on.
2. **Skips** anything you've already seen or already applied to.
3. **Filters** down to roles that match the job titles, skills and locations you care about.
4. **Saves** the survivors into an Airtable table you can browse, with `Status = New` and a **Match Score** (0-100) so the best fits can sit at the top.

You review the results in Airtable whenever you like. There's no AI, no API costs, and nothing to babysit. It runs by itself on a free GitHub schedule.

> **New to GitHub, Airtable or all of this?** Don't start here. Open **[SETUP.md](SETUP.md)** instead. It walks you through everything click by click, start to finish, assuming no prior experience. This README is the quick reference for once you're set up.

## What you'll need

Three free accounts. That's it.

- A **GitHub** account (runs the pipeline for free on a schedule)
- An **Airtable** account (stores the jobs it finds)
- A **Gmail** account that receives LinkedIn / Indeed job-alert emails

No credit card, no paid tier, no AI keys.

## How it fits together

```
LinkedIn + Indeed alert emails ─┐
Greenhouse / Lever / Ashby /     │
SmartRecruiters / Workday      ├─►  pipeline  ─►  filters  ─►  Airtable "Pipeline" table
careers pages                   │                                   (you review here)
Built In (optional)            ─┘
```

## Repo layout

```
.
├── .github/workflows/job_pipeline.yml   # the daily schedule (runs the pipeline)
├── pipeline/
│   ├── main.py                          # the entry point that ties it together
│   ├── config.py                        # ★ the only file you normally edit ★
│   ├── models.py                        # the shape of a single job posting
│   ├── location.py                      # turns a messy location string into city/state/country
│   ├── filter.py                        # title + location + skill matching
│   ├── airtable_client.py               # reads/writes Airtable, handles de-duplication
│   └── sources/
│       ├── gmail_parser.py              # reads LinkedIn + Indeed alert emails
│       ├── greenhouse.py
│       ├── lever.py
│       ├── ashby.py
│       ├── smartrecruiters.py
│       ├── workday.py               # optional: big employers on Workday
│       └── builtin.py               # optional: the Built In job site
├── requirements.txt                     # the Python libraries it uses
├── .env.example                         # a template for running it on your own computer
├── README.md                            # this file
└── SETUP.md                             # the full step-by-step setup guide
```

## The four secrets it needs

The pipeline reads everything sensitive from "secrets" so nothing private is ever written into the code. You add these once in your GitHub repo under **Settings → Secrets and variables → Actions** (SETUP.md shows you exactly where):

| Secret | What it is | Where it comes from |
|---|---|---|
| `AIRTABLE_API_KEY` | Your Airtable access token (starts with `pat…`) | airtable.com/create/tokens |
| `AIRTABLE_BASE_ID` | Your Airtable base ID (starts with `app…`) | the URL of your base |
| `GMAIL_ADDRESS` | The Gmail address that gets your job alerts | you already have it |
| `GMAIL_APP_PASSWORD` | A 16-character Gmail "App Password" | myaccount.google.com/apppasswords |

## Running it

**Daily (automatic).** Once the secrets and schedule are in place, GitHub runs it every day on its own. You don't do anything.

**On demand (to test).** Go to the **Actions** tab in your repo, click **Job Pipeline** in the left sidebar, then **Run workflow**. Watch the log; it prints how many jobs each source returned and how many were dropped at each filter step.

## What gets kept (the filter rules)

A role is saved only if **all** of these are true:

1. **Title** matches at least one entry in `TARGET_TITLES` and none of `EXCLUDE_TITLE_TERMS`.
2. **Location** is onsite/hybrid in one of your `ALLOWED_ONSITE_LOCATIONS`, **or** remote. With `REMOTE_US_ONLY = True` (the default), remote jobs based outside the US are dropped. Remote is read from the job's location and the job board's own remote setting, not from the description text.
3. **Core stack**: at least `MIN_CORE_STACK_MATCHES` (default 1) of `CORE_STACK_KEYWORDS` appears in the title or description. These are the specific tools that signal a real fit.
4. **Broad signal**: at least `MIN_BROAD_SKILL_MATCHES` (default 3) of `BROAD_SKILL_KEYWORDS` appears. These are broader data-analyst signals.

Rules 3 and 4 are skipped for LinkedIn/Indeed email rows, because alert emails don't include a job description. For those, your alert settings on LinkedIn/Indeed are doing the pre-filtering.

Every kept row also records **which** keywords matched, in a "Matched Skills" field, so you can see *why* a job passed and spot any false positives at a glance.

**Match Score.** Each kept job gets a score from 0 to 100: it starts at `SCORE_BASE` (50) and earns points for every Tier 1 and Tier 2 keyword in the description. Sort the Pipeline table by Match Score (highest first) to see the strongest fits first. Email-alert jobs have no description, so they get the base score. The score is saved only if your Pipeline table has a `Match Score` field (optional, see the schema below).

## Customizing it

Open **`pipeline/config.py`**. Everything you'd want to change is there, with comments:

- `TARGET_TITLES` and `EXCLUDE_TITLE_TERMS`: the titles you want and the ones you don't.
- `ALLOWED_ONSITE_LOCATIONS`: your city, lowercase (e.g. `["chicago"]`). Set it to `[]` to keep only remote roles.
- `CORE_STACK_KEYWORDS` / `BROAD_SKILL_KEYWORDS` and their `MIN_*_MATCHES` thresholds: the tools and signals from your own resume. Lower a threshold or add tools to widen the net. Raise it or remove tools to tighten.
- `TARGET_COMPANIES`: the companies whose careers pages get polled. The list shipped here is just an example. Replace it with companies you care about.
- `WORKDAY_COMPANIES` and `WORKDAY_SEARCH_TERMS`: large employers whose careers pages run on Workday. Examples are included, switched off; remove the `# ` in front of a line to turn it on.
- `BUILTIN_ENABLED` and `BUILTIN_SITE`: turn on the Built In job site and pick the national site or your city's.
- `EXCLUDE_COMPANIES`: companies to always skip, such as your current employer.
- `REMOTE_US_ONLY`: set to `False` if you're open to remote jobs based in any country.

The log line `Pre-filter: N in, M out (dropped X on title, Y on location, …, excluded company)` tells you where roles are dropping, so you can tune from real numbers.

## Airtable schema (what tables/fields to create)

The pipeline writes to one base with **three tables**. SETUP.md walks you through creating them, but here's the reference. The **Pipeline** table is where results land:

| Field | Type | Notes |
|---|---|---|
| Job Title | Single line text | primary field |
| Company | Link to **Companies** table | |
| Job ID | Single line text | used to avoid duplicates |
| Location | Single line text | raw text from the source |
| Remote Type | Single select | Remote / Hybrid / Onsite |
| Source | Single select | LinkedIn Email / Indeed Email / Greenhouse / Lever / Ashby / SmartRecruiters / Workday / Built In |
| URL | URL | used to avoid duplicates |
| Salary Range | Single line text | "N/A" if the source didn't list one |
| Posted Date | Date | when the role went live |
| Found Date | Date | when the pipeline saw it |
| Status | Single select | New / Reviewing / Applied / Skipped / Archived |
| Matched Skills | Long text | which keywords matched (shows *why* it passed) |
| Region | Single select | US / UK / Canada / EU / LATAM / APAC / ANZ / MENA / Africa / Global / Other |
| Country | Single line text | parsed from Location |
| State | Single line text | US two-letter code, US roles only |
| City | Single line text | parsed from Location |
| Match Score | Number (integer) | **optional**. 0-100, sort highest first. Skipped if the field doesn't exist |

Plus a **Companies** table (one field: `Company Name`) and a **Job Applications** table (`Job Title` + a `Company` link). The pipeline reads those two to avoid re-surfacing jobs you've already tracked or applied to.

> ⚠️ Field names must match **exactly**, including capitalization. Airtable silently ignores writes to fields that don't exist, so a typo means data quietly goes missing. SETUP.md lists every field to create.

## Good habits

- **Don't delete rows from the Pipeline table.** De-duplication reads every row regardless of status. To make a job stop coming back, set its `Status` to `Archived` rather than deleting it. Deleting removes the "already seen" memory and the job returns on the next run.
- **If a company suddenly returns zero jobs**, it probably switched applicant-tracking systems. Check its careers page, find the new slug, and update the tuple in `TARGET_COMPANIES`. If it moved to Workday, add it to `WORKDAY_COMPANIES` instead (the comment above that list shows how to read the tenant, number and site from the careers-page address). For any other system, just comment that line out.
- **If the schedule stops running**, GitHub auto-pauses scheduled workflows after 60 days with no repo activity. Push any small change, or re-enable it from the Actions tab.

## Cost

Free. No AI calls. The GitHub Actions free tier covers a once-a-day run, and the Airtable and Gmail free tiers comfortably cover the volume.
