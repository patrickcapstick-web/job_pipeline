"""
Configuration for the job pipeline.

================================================================================
THIS IS THE ONLY FILE YOU NORMALLY NEED TO EDIT.
================================================================================
Everything here controls what the pipeline considers a "fit": which job titles
to look for, which skills/tools matter, which locations are acceptable, and
which companies to poll. The values below are a working EXAMPLE aimed at a
senior data-analyst search. Replace them with whatever fits the roles you want.

Nothing sensitive lives here. API keys and passwords are read from environment
variables (see README.md / SETUP.md), never from this file.
"""

# How far back to look for new postings (in days).
# With daily runs, a 1-day lookback covers everything that arrived since
# yesterday's run. If a run is ever skipped, jobs from that day are missed.
LOOKBACK_DAYS = 1

# -----------------------------------------------------------------------------
# Target role titles - matched (whole-word) against the job title.
# A title only needs to match ONE of these to pass the title filter.
# EDIT THIS LIST to the titles you actually want.
# -----------------------------------------------------------------------------
TARGET_TITLES = [
    # Senior Data Analyst (and Sr/Lead/Staff/Principal variants)
    "senior data analyst",
    "sr data analyst",
    "sr. data analyst",
    "lead data analyst",
    "staff data analyst",
    "principal data analyst",

    # Analytics Engineer (any level)
    "analytics engineer",

    # Data Scientist (rely on EXCLUDE below to filter junior/entry)
    "data scientist",

    # Specialty Senior Analyst tracks
    "senior product analyst",
    "sr product analyst",
    "sr. product analyst",
    "senior business analyst",
    "sr business analyst",
    "sr. business analyst",
    "senior operations analyst",
    "sr operations analyst",
    "sr. operations analyst",
    "senior insights analyst",
    "sr insights analyst",
    "sr. insights analyst",

    # Strategy / Operations Analyst
    "strategy and operations",
    "strategy & operations",
    "strategy analyst",

    # Fraud / Risk / Disputes specialist tracks (example domain, edit freely)
    "fraud analyst",
    "senior fraud analyst",
    "sr fraud analyst",
    "disputes specialist",
    "disputes analyst",

    # Manager tracks
    "analytics manager",
    "insights manager",
    "data analytics manager",
    "continuous improvement analyst",
    "continuous improvement manager",
]

# -----------------------------------------------------------------------------
# Auto-exclude: if any of these terms appear in the title, drop the role.
# Runs AFTER target match, so a role like "Senior Sales Analyst" is excluded
# even if it superficially matches "senior analyst".
#
# Terms are matched with whole-word logic (see filter.py _word_match), not bare
# substrings, so single words like "sales" or "chief" won't match inside other
# words. EDIT THIS LIST to fit the levels and functions you want to avoid.
# -----------------------------------------------------------------------------
EXCLUDE_TITLE_TERMS = [
    # Junior levels
    "junior",
    "jr",
    "entry-level",
    "entry level",
    "intern",      # matches "intern"; "internal" is a separate word under whole-word matching

    # Executive levels (above where this example search is aimed)
    "director",
    "vp",
    "vice president",
    "head of",
    "c-suite",
    "chief",

    # Wrong functions
    "sales",
    "engineering manager",
    "software engineer",
    "ml engineer",
    "machine learning engineer",
    "research scientist",
]

# -----------------------------------------------------------------------------
# Companies to skip entirely, from every source. Handy for your current
# employer. Lowercase, one per line, e.g. ["acme", "globex"]. Matched as a
# whole word, so "acme" also skips "Acme Labs" but not "Acmeville".
# -----------------------------------------------------------------------------
EXCLUDE_COMPANIES = []

# -----------------------------------------------------------------------------
# Two-tier skill filter.
#
# Tier 1 (CORE_STACK_KEYWORDS): the specific tools/methods that signal a role is
# really in your wheelhouse. A role must mention AT LEAST ONE of these. This is
# what prevents jobs at companies with a totally different stack from passing
# just because they say "SQL" and "stakeholder."
#
# Tier 2 (BROAD_SKILL_KEYWORDS): general signals that the role is genuinely
# data-analyst shaped (domain terms, methodologies, modern AI awareness).
# A role must hit AT LEAST MIN_BROAD_SKILL_MATCHES of these.
#
# Both tiers must pass. Generic terms like "stakeholder", "cross-functional",
# "kpi", and "dashboard" are deliberately NOT here because they appear in every
# analyst posting and provide no filtering signal.
#
# EDIT THESE LISTS to the tools and signals on your own resume. The example
# values below cover a modern analytics stack PLUS common enterprise BI tools
# (Power BI, SQL Server, SAS, Qlik) so cross-industry roles aren't dropped just
# for being on a different stack.
#
# WHOLE-WORD-MATCH CAUTION: filter.py matches keywords as whole words/phrases.
# Short tokens can still be risky if written as bare substrings, so some terms
# below are written as longer phrases (e.g. "sas programming" rather than bare
# "sas", which would otherwise match inside "Kansas"/"SaaS"). Keep that in mind
# if you add short keywords of your own.
# -----------------------------------------------------------------------------
CORE_STACK_KEYWORDS = [
    # Modern analytics/data stack (example)
    "snowflake",
    "looker",
    "lookml",
    "tableau",
    "dbt",
    "airflow",
    "lean six sigma",
    "dmaic",
    # "mode" matches only as a standalone word (not inside "model"/"modern").
    "mode",
    # Enterprise BI/analytics tools (cross-industry peers of the stack above)
    "power bi",
    "powerbi",
    "sql server",
    "qlik",
    "sas programming",  # phrased to avoid matching "Kansas"/"SaaS"; do NOT shorten to bare "sas"
    "base sas",         # common posting phrasing for the SAS language
]
MIN_CORE_STACK_MATCHES = 1

BROAD_SKILL_KEYWORDS = [
    # SQL is broad but expected; a reasonable Tier 2 signal, not a Tier 1 differentiator
    "sql",
    "etl",
    "elt",
    "data warehouse",
    "data model",
    "semantic layer",
    # Domain terms (example: fintech/payments). Swap for your own industry
    "fraud",
    "risk",
    "disputes",
    "chargeback",
    # Methodology
    "experimentation",
    "a/b test",
    "ab test",
    "hypothesis test",
    "root cause",
    "continuous improvement",
    "process improvement",
    # Statistical process control / quality (strong cross-industry signal:
    # manufacturing, healthcare, operations)
    "statistical process control",
    "control chart",
    "spc",              # short, but low collision risk; watch the logs on the first run
    "kaizen",
    "six sigma",
    "data governance",
    "data quality",
    # Ingestion / pipeline tooling
    "fivetran",
    # Modern AI awareness
    "generative ai",
    "llm",
    "agentic",
    "prompt engineering",
    "openai",
    "anthropic",
    "claude",
    "chatgpt",
    # Self-serve / democratization
    "self-serve",
    "data democratization",
    "data literacy",
]
MIN_BROAD_SKILL_MATCHES = 3

# -----------------------------------------------------------------------------
# Match Score (0-100), written to the optional "Match Score" field in Airtable
# so you can sort the best fits to the top. Every job that passes starts at
# SCORE_BASE, then earns points for each Tier 1 and Tier 2 keyword found in the
# description, up to a cap. Format: (points per keyword, most points possible).
# Jobs from email alerts have no description, so they just get SCORE_BASE.
# -----------------------------------------------------------------------------
SCORE_BASE = 50
SCORE_CORE_POINTS = (6, 25)
SCORE_BROAD_POINTS = (3, 25)

# -----------------------------------------------------------------------------
# Location filter
# -----------------------------------------------------------------------------
# A role passes the location filter if ANY of these are true:
#   1. The role is remote (signal found in title, location, or remote_type)
#   2. The role's location contains one of ALLOWED_ONSITE_LOCATIONS (case-insensitive)
# Onsite or hybrid roles outside those locations are dropped.
#
# >>> EDIT THIS <<< Replace "chicago" with your own city (lowercase). You can
# list more than one, e.g. ["chicago", "milwaukee"]. To keep ONLY remote roles
# and drop all onsite/hybrid, set this to an empty list: []
ALLOWED_ONSITE_LOCATIONS = [
    "chicago",
]

# Substrings that count as a remote signal when found in the title or location string.
REMOTE_KEYWORDS = [
    "remote",
    "anywhere",
    "work from home",
    "wfh",
    "distributed",
    "fully remote",
]

# Keep only remote jobs open to people in the United States. With True, a
# job listed as "Remote Spain", "Canada - Remote" or "Remote, Bangalore" is
# dropped. Set to False if you are outside the US or open to any country.
REMOTE_US_ONLY = True

# Non-US cities that mark a remote job as outside the US (used only when
# REMOTE_US_ONLY is True). Countries and regions are already detected
# automatically; this list catches city-only locations.
NON_US_CITY_TERMS = [
    "bangalore", "bengaluru", "hyderabad", "mumbai", "pune", "delhi",
    "london", "dublin", "toronto", "vancouver", "montreal", "sydney",
    "melbourne", "singapore", "tokyo", "berlin", "amsterdam", "paris",
    "barcelona", "madrid", "warsaw", "sao paulo", "mexico city", "tel aviv",
]

# -----------------------------------------------------------------------------
# Target companies for ATS polling.
# Format: (display_name, ats, slug)
# - display_name: how it appears in Airtable
# - ats: 'greenhouse' | 'lever' | 'ashby' | 'smartrecruiters'
# - slug: the company's ATS path slug (the part after the ATS domain in the
#         company's careers-page URL)
#
# This is an EXAMPLE starter list. Add/remove companies you care about. Find a
# company's slug from its careers page URL:
#   Greenhouse:       boards.greenhouse.io/<slug>
#   Lever:            jobs.lever.co/<slug>
#   Ashby:            jobs.ashbyhq.com/<slug>
#   SmartRecruiters:  jobs.smartrecruiters.com/<slug>
#
# Status legend in comments (from prior runs):
#   [ok]    = verified returning postings
#   [fixed] = slug or ATS corrected after a 404
#   [?]     = unverified guess; will just log a 404 if wrong, no harm
# -----------------------------------------------------------------------------
TARGET_COMPANIES = [
    # Fintech / Payments
    ("Stripe", "greenhouse", "stripe"),                  # [ok]
    ("Plaid", "ashby", "plaid"),                         # [fixed] moved Lever -> Ashby (Sept 2026)
    ("Mercury", "ashby", "mercury"),                     # [ok]
    ("Brex", "greenhouse", "brex"),                      # [ok]
    ("Ramp", "ashby", "ramp"),                           # [ok]
    ("Chime", "greenhouse", "chime"),                    # [ok]
    ("Affirm", "greenhouse", "affirm"),                  # [ok]
    ("Robinhood", "greenhouse", "robinhood"),            # [ok]
    # Marqeta: board stopped responding (404) in Sept 2026 and no replacement was found.
    ("Modern Treasury", "ashby", "moderntreasury"),      # [fixed] moved from Greenhouse to Ashby

    # Tech / SaaS
    ("Notion", "ashby", "notion"),                       # [ok]
    ("Linear", "ashby", "linear"),                       # [ok]
    ("Vercel", "greenhouse", "vercel"),                  # [ok]
    ("Datadog", "greenhouse", "datadog"),                # [ok]
    # dbt Labs: board stopped responding (404) in Sept 2026 and no replacement was found.
    ("HubSpot", "greenhouse", "hubspot"),                # [ok]
    ("Asana", "greenhouse", "asana"),                    # [ok]
    ("Figma", "greenhouse", "figma"),                    # [ok]
    ("Anthropic", "greenhouse", "anthropic"),            # [ok]
    ("OpenAI", "ashby", "openai"),                       # [fixed] was Greenhouse, actually on Ashby

    # SmartRecruiters
    ("Atlassian", "smartrecruiters", "atlassian"),       # [fixed] moved from Lever (returned 0) to SmartRecruiters
    ("Visa", "smartrecruiters", "visa"),                 # [?] verified slug; first run will confirm
    ("McDonald's Corporation", "smartrecruiters", "mcdonaldscorporation"),  # [?] verified slug; first run will confirm

    # Marketplaces / Consumer
    ("DoorDash", "greenhouse", "doordashusa"),           # [fixed] slug is "doordashusa" not "doordash"
    ("Instacart", "greenhouse", "instacart"),            # [ok]
    ("Lyft", "greenhouse", "lyft"),                      # [ok]
    ("Airbnb", "greenhouse", "airbnb"),                  # [ok]
    ("Pinterest", "greenhouse", "pinterest"),            # [ok]
    ("Reddit", "greenhouse", "reddit"),                  # [ok]

    # Healthtech
    ("Oscar Health", "greenhouse", "oscar"),             # [ok]
    ("Headway", "ashby", "headway"),                     # [ok]
    ("Hims", "ashby", "hims-and-hers"),                  # [fixed] moved from Greenhouse to Ashby
    ("Ro", "lever", "ro"),                               # [fixed] on Lever as "ro"
    ("Cedar", "greenhouse", "careportalinc"),            # [fixed] on Greenhouse as "careportalinc"

    # E-commerce / Retail
    ("Faire", "greenhouse", "faire"),                    # [ok]
    ("Klaviyo", "greenhouse", "klaviyo"),                # [ok]

    # Ops / Analytics-heavy
    ("Carta", "greenhouse", "carta"),                    # [ok]
    ("Gusto", "greenhouse", "gusto"),                    # [?] may be on its own ATS now
    ("Vanta", "ashby", "vanta"),                         # [ok]
    ("Scale AI", "greenhouse", "scaleai"),               # [fixed] was Ashby, actually on Greenhouse
]

# -----------------------------------------------------------------------------
# Workday companies (optional).
#
# Many large employers (banks, insurers, retailers, healthcare) post jobs on
# Workday instead of the job boards above. To add one, open its careers page
# and look at the address. It looks like:
#     https://allstate.wd5.myworkdayjobs.com/allstate_careers
#             ^^^^^^^^  ^                      ^^^^^^^^^^^^^^^^
#             tenant    number                 site
# Then add a line in this format:  ("Display name", "tenant|number|site"),
#
# Workday boards are huge, so the pipeline does not read every job. It runs
# each of WORKDAY_SEARCH_TERMS as a search on each company's board and only
# opens jobs whose titles match TARGET_TITLES. Use short phrases close to the
# titles you want.
#
# The lines below were all confirmed working in Sept 2026. Remove the "# " at
# the start of a line to turn that company on.
# -----------------------------------------------------------------------------
WORKDAY_COMPANIES = [
    # ("Allstate", "allstate|5|allstate_careers"),
    # ("Capital One", "capitalone|12|Capital_One"),
    # ("Morningstar", "morningstar|5|Americas"),
    # ("Motorola Solutions", "motorolasolutions|5|Careers"),
    # ("TransUnion", "transunion|5|TransUnion"),
    # ("CDW", "cdw|5|Careers"),
    # ("Abbott", "abbott|5|abbottcareers"),
    # ("Zendesk", "zendesk|1|Zendesk"),
    # ("Chewy", "chewy|5|External"),
    # ("Etsy", "etsy|5|Etsy_Careers"),
    # ("Zillow", "zillow|5|Zillow_Group_External"),
    # ("PayPal", "paypal|1|jobs"),
    # ("Mastercard", "mastercard|1|CorporateCareers"),
    # ("Salesforce", "salesforce|12|External_Career_Site"),
    # ("Adobe", "adobe|5|external_experienced"),
    # ("Target", "target|5|targetcareers"),
    # ("Humana", "humana|5|Humana_External_Career_Site"),
]
WORKDAY_SEARCH_TERMS = [
    "data analyst", "business analyst", "product analyst", "insights",
    "analytics manager", "strategy operations",
]
WORKDAY_MAX_PAGES = 2   # pages of 20 results read per search term

# -----------------------------------------------------------------------------
# Built In (optional). Built In is a job site for tech and startup jobs, with a
# national site and several city sites. When turned on, the pipeline runs each
# of BUILTIN_SEARCH_TERMS there once a day and opens only jobs whose titles
# match TARGET_TITLES.
#
# To turn it on: set BUILTIN_ENABLED = True and pick the site for your area:
#   "https://builtin.com"                 (all US)
#   "https://www.builtinchicago.org"      "https://www.builtinnyc.com"
#   "https://www.builtinaustin.com"       "https://www.builtinboston.com"
#   "https://www.builtinla.com"           "https://www.builtinseattle.com"
#   "https://www.builtinsf.com"           "https://www.builtincolorado.com"
# -----------------------------------------------------------------------------
BUILTIN_ENABLED = False
BUILTIN_SITE = "https://builtin.com"
BUILTIN_SEARCH_TERMS = [
    "senior data analyst", "business analyst", "product analyst",
    "analytics manager", "insights", "strategy operations",
]
BUILTIN_MAX_PAGES = 2   # pages of 25 results read per search term

# -----------------------------------------------------------------------------
# Gmail search queries for alert-email parsing.
# These are passed straight to Gmail's search. The defaults match the standard
# "from" addresses LinkedIn and Indeed use for job-alert emails.
# -----------------------------------------------------------------------------
GMAIL_LINKEDIN_QUERY = 'from:jobalerts-noreply@linkedin.com'
GMAIL_INDEED_QUERY = 'from:alert@indeed.com OR from:noreply@indeed.com'
