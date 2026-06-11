# Setup guide (start here)

This guide takes you from nothing to a working, self-running job pipeline. It assumes you have never used GitHub or Airtable before. You will not need to write any code or use a "command line." Everything happens in your web browser by clicking buttons.

**Time:** about 45 to 60 minutes, once.
**Cost:** free.
**What you'll create:** three free accounts (GitHub, Airtable, a Gmail app password), and a copy of this project that runs by itself once a day.

Work through the parts in order. Each part ends with a short "you should now have" checkpoint so you can confirm you are on track before moving on.

---

## The big picture (read this once)

There are three moving pieces:

1. **GitHub** holds the code and runs it for you, free, on a daily timer.
2. **Airtable** is a spreadsheet-like app where the jobs it finds get saved for you to review.
3. **Gmail** receives your LinkedIn and Indeed job-alert emails, which the pipeline reads.

You connect them by giving GitHub four "secrets" (an Airtable key, an Airtable base ID, your Gmail address and a Gmail app password). After that it runs on its own.

You do not have to understand the code. You only ever edit one settings file, and only if you want to change which jobs it looks for.

---

## Part 1: Get your own copy of the project on GitHub

### 1.1 Make a GitHub account

1. Go to https://github.com and click **Sign up**.
2. Follow the prompts (email, password, username). The free plan is all you need.
3. Verify your email when GitHub asks.

### 1.2 Copy this project into your account

You want your **own** copy so you can add your private settings to it.

1. Open the project page (the person who shared this with you will give you the link, it looks like `https://github.com/their-name/curious_squid`).
2. Look near the top right for a green **Use this template** button and click it, then choose **Create a new repository**.
   - If you do not see "Use this template," click **Fork** instead (top right). A fork is just a personal copy. It works the same way for our purposes.
3. Give your copy a name (for example `my-job-pipeline`). Leave it set to **Public**.
   - Public is correct and safe. Public repositories get **unlimited free** daily runs. Your secrets stay encrypted and are never visible to anyone, including you, after you save them (more on that in Part 6).
4. Click **Create repository**.

### 1.3 Turn on the automation

GitHub disables the automatic runner on brand-new copies until you say it is OK.

1. In your new repository, click the **Actions** tab (along the top).
2. If you see a green button that says something like **I understand my workflows, go ahead and enable them**, click it.
3. You should now see a workflow named **Job Pipeline** listed on the left.

**You should now have:** your own copy of the project on GitHub, with the Actions tab showing a workflow called "Job Pipeline." Do not run it yet. It will fail until you finish the next parts.

---

## Part 2: Build your Airtable base

This is the most detailed part. Take it slowly. The pipeline writes its results into Airtable, and it expects specific table names and field names. **Spelling and capitalization must match exactly.** If a field name is even slightly off, Airtable quietly ignores it and that piece of data goes missing with no error.

### 2.1 Make an Airtable account and a base

1. Go to https://airtable.com and sign up (free).
2. On your home screen, click **Create** or the **+** to make a new, empty **base**. A "base" is just an Airtable file that can hold several tables.
3. Name the base anything you like, for example `Job Search`.

### 2.2 Create the three tables

A new base starts with one table (probably called "Table 1"). You need three tables with these exact names:

- `Pipeline`
- `Companies`
- `Job Applications`

To rename the first table: double-click its tab at the bottom (or top) and type `Pipeline`.
To add the others: click the **+** next to the table tabs, and name them `Companies` and `Job Applications`.

> Exact names matter: `Pipeline` not `pipeline` or `Pipelines`.

### 2.3 Set up the **Companies** table

This one is simple.

1. Open the **Companies** table.
2. It already has a first column (the "primary field"). Rename it to exactly `Company Name`. (Double-click the column header to rename.)
3. Delete any other default columns (Notes, Attachments, etc.) if you like. They do no harm if left.

### 2.4 Set up the **Job Applications** table

1. Open the **Job Applications** table.
2. Rename the primary (first) column to exactly `Job Title`.
3. Add one more field named exactly `Company`, and set its type to **Link to another record**, linked to the **Companies** table.
   - To add a field: click the **+** at the right end of the column headers, type the name `Company`, choose the field type **Link to another record**, then pick **Companies**.

You can leave this table empty. The pipeline only reads it, to avoid re-showing you jobs you have already logged here.

### 2.5 Set up the **Pipeline** table (the important one)

This is where found jobs land. Create each field below with the **exact** name and the listed type. The first one already exists as the primary column, just rename it.

| # | Field name (exact) | Field type | How to set the type |
|---|---|---|---|
| 1 | `Job Title` | Single line text | (this is the primary column, just rename it) |
| 2 | `Company` | Link to another record | link it to the **Companies** table |
| 3 | `Job ID` | Single line text | |
| 4 | `Location` | Single line text | |
| 5 | `Remote Type` | Single select | add options: `Remote`, `Hybrid`, `Onsite` |
| 6 | `Source` | Single select | add options: `LinkedIn Email`, `Indeed Email`, `Greenhouse`, `Lever`, `Ashby`, `SmartRecruiters` |
| 7 | `URL` | URL | |
| 8 | `Salary Range` | Single line text | |
| 9 | `Posted Date` | Date | |
| 10 | `Found Date` | Date | |
| 11 | `Status` | Single select | add options: `New`, `Reviewing`, `Applied`, `Skipped`, `Archived` |
| 12 | `Matched Skills` | Long text | |
| 13 | `Region` | Single select | add options: `US`, `UK`, `Canada`, `EU`, `LATAM`, `APAC`, `ANZ`, `MENA`, `Africa`, `Global`, `Other` |
| 14 | `Country` | Single line text | |
| 15 | `State` | Single line text | |
| 16 | `City` | Single line text | |

Tips:
- For **Single select** fields you do not strictly have to pre-add every option. The pipeline is allowed to create missing options automatically. But adding `Remote / Hybrid / Onsite` and the `Status` options yourself gives you tidy colors and avoids surprises.
- To add a field: click the **+** at the end of the header row, type the exact name, pick the type, then save.
- Double-check field 12 is spelled `Matched Skills` (capital M, capital S, a space between). This is the field that records *why* a job passed the filter, and a typo here means that information silently disappears.

**You should now have:** one Airtable base with three tables (`Pipeline`, `Companies`, `Job Applications`), the Pipeline table carrying all 16 fields above, and the two link fields pointing at `Companies`.

---

## Part 3: Get your Airtable key and base ID

The pipeline needs two things from Airtable: a key that lets it write to your base, and the base's ID so it knows which base.

### 3.1 The base ID (starts with `app…`)

1. Open your base in the browser.
2. Look at the address bar. The URL looks like `https://airtable.com/appXXXXXXXXXXXXXX/tblYYYY...`.
3. The part that starts with `app` (for example `appwI8kS2nQ1bExmP`) is your **base ID**. Copy it somewhere safe for a moment.

### 3.2 The access token (starts with `pat…`)

1. Go to https://airtable.com/create/tokens
2. Click **Create new token**.
3. Give it a name, for example `job pipeline`.
4. Under **Scopes**, add these three:
   - `data.records:read`
   - `data.records:write`
   - `schema.bases:read`
5. Under **Access**, click **Add a base** and choose the base you built in Part 2.
6. Click **Create token**. Airtable shows you the token (it starts with `pat`) **once**. Copy it immediately and keep it somewhere safe for the next few minutes. If you lose it, just create another.

**You should now have:** a base ID starting with `app…` and a token starting with `pat…`, both copied somewhere temporary.

---

## Part 4: Create a Gmail App Password

The pipeline reads your LinkedIn and Indeed alert emails. To let it sign in safely, Google gives you a special 16-character "app password" that works only for this and can be revoked anytime. It is not your normal Gmail password.

> App passwords require 2-Step Verification to be on. If it is not on yet, you will turn it on first.

1. Go to https://myaccount.google.com/security
2. Find **2-Step Verification** and turn it on if it is not already. Follow Google's prompts (usually a phone number or prompt).
3. Now go to https://myaccount.google.com/apppasswords
4. If asked, sign in again. Give the app password a name like `job pipeline` and click **Create**.
5. Google shows a 16-character password in four blocks of four (like `abcd efgh ijkl mnop`). Copy it and **remove the spaces**, so it becomes `abcdefghijklmnop`. Keep it safe for the next part.

Also note the Gmail address itself (for example `you@gmail.com`). You will need both.

**You should now have:** your Gmail address, and a 16-character app password with the spaces removed.

---

## Part 5: Turn on the job alerts that feed the pipeline

The pipeline reads alert emails, so those alerts have to actually be arriving in the Gmail inbox from Part 4.

- **LinkedIn:** search for a job title you want, open the search, and turn on the **job alert** toggle (LinkedIn will email you matches). Set it to a daily alert if offered. Do this for each title you care about.
- **Indeed:** run a search at https://indeed.com, then look for a **"Get new jobs for this search by email"** style link and set up the alert.

If you would rather skip email alerts entirely, the pipeline still works using only the company careers pages (Greenhouse, Lever, Ashby, SmartRecruiters). The Gmail secrets are still required for the program to start, but it will simply find zero email jobs if no alerts arrive. That is fine.

**You should now have:** at least one LinkedIn and/or Indeed alert arriving in your Gmail. (They take a day or two to start flowing. You do not have to wait for them to continue setup.)

---

## Part 6: Give the four secrets to GitHub

Now you hand GitHub the four values so it can run on your behalf. These are stored encrypted. After you save one, GitHub never shows it again, not even to you. Nobody who looks at your public repo can see them.

1. Go back to your repository on GitHub (the copy from Part 1).
2. Click **Settings** (top right of the repo).
3. In the left sidebar, click **Secrets and variables**, then **Actions**.
4. Click **New repository secret**. Add each of the four below, one at a time. The **Name** must be typed exactly as shown (all capitals, with underscores).

| Name (type exactly) | Value (paste your value) |
|---|---|
| `AIRTABLE_API_KEY` | your `pat…` token from Part 3.2 |
| `AIRTABLE_BASE_ID` | your `app…` base ID from Part 3.1 |
| `GMAIL_ADDRESS` | your Gmail address, e.g. `you@gmail.com` |
| `GMAIL_APP_PASSWORD` | the 16-character app password from Part 4 (no spaces) |

For each: type the **Name**, paste the **Value**, click **Add secret**. Repeat until all four are listed.

**You should now have:** four secrets listed on the Actions secrets page: `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`.

---

## Part 7: Tell it what jobs you want (edit one file)

The project ships with example settings aimed at a senior data-analyst search. You will almost certainly want to change the titles, your city and the skills. You can edit the file directly on the GitHub website, no download needed.

1. In your repository, click the **pipeline** folder, then click the file **config.py**.
2. Click the **pencil icon** (Edit this file) near the top right of the file view.
3. Change the parts you care about. The most useful three:
   - **`ALLOWED_ONSITE_LOCATIONS`**: replace `"chicago"` with your own city in lowercase, for example `"austin"`. To keep **only** remote roles, change it to an empty list: `ALLOWED_ONSITE_LOCATIONS = []`.
   - **`TARGET_TITLES`**: the list of job titles to look for. Add or remove lines so it matches the roles you want. Keep each title in quotes and lowercase.
   - **`TARGET_COMPANIES`**: the companies whose careers pages get checked. The shipped list is just an example. You can leave it for now and refine later.
4. When done, scroll down and click **Commit changes** (green button). "Commit" just means "save." A short note like "update my settings" is fine.

Everything in `config.py` has comments explaining it. You do not have to change anything beyond the three items above to get going.

**You should now have:** a `config.py` saved with at least your own city (or an empty list for remote-only) and your target titles.

---

## Part 8: Run it once, by hand, to test

You do not have to wait for the daily timer. Trigger a run now to confirm everything is wired up.

1. Click the **Actions** tab.
2. In the left sidebar, click **Job Pipeline**.
3. On the right, click **Run workflow**, then the green **Run workflow** button in the little popup. Leave the branch as the default.
4. Wait a few seconds and refresh. A new run appears (a yellow dot means running, green check means success, red X means it hit an error).
5. Click the run, then click the **run-pipeline** job to see the log. Scroll through it. You are looking for lines like:
   - `Source totals: N postings collected`
   - `Pre-filter: N in, M out (dropped X on title, Y on location, ...)`
   - `Run complete. Wrote M new Pipeline rows.`

If it finished green and wrote some rows, you are done. If it went red, see Part 10.

> It is normal for an early run to write **zero** rows, especially before your email alerts have started arriving and if your filters are strict. A green run that wrote zero rows means the plumbing works. You can loosen the filters later (Part 9).

**You should now have:** at least one green (successful) run in the Actions tab.

---

## Part 9: Review your results and tune

1. Open your Airtable base and the **Pipeline** table. New jobs appear with `Status = New`.
2. For each job, read the **Matched Skills** field to see why it passed, click the **URL** to view the posting, and set **Status** to `Reviewing`, `Applied`, `Skipped` or `Archived` as you go.

**Getting too few results?** Loosen the filters in `config.py` (Part 7 shows you how to edit it):
- Lower `MIN_BROAD_SKILL_MATCHES` from `3` to `2`.
- Add more titles to `TARGET_TITLES`.
- Add your city, or set `ALLOWED_ONSITE_LOCATIONS = []` to allow all remote roles.

**Getting too much junk?** Tighten them:
- Raise `MIN_BROAD_SKILL_MATCHES`.
- Add unwanted words to `EXCLUDE_TITLE_TERMS`.
- Trim `TARGET_TITLES` down to fewer, more specific titles.

The log line `Pre-filter: N in, M out (dropped X on title, Y on location, Z on core stack, W on broad skills)` tells you exactly where jobs are being dropped, so you can adjust the right knob.

> One habit to keep: do **not delete** rows from the Pipeline table. To make a job stop reappearing, set its `Status` to `Archived`. Deleting it erases the "already seen" memory and it comes back on the next run.

**That's it.** From here on it runs by itself once a day. You just check Airtable.

---

## Part 10: If something goes wrong

**The run is red (failed).** Click the failed run, open the **run-pipeline** job, and read the last lines of the log. Common causes:

- `missing required env var ...` : one of the four secrets in Part 6 is missing or its **Name** is misspelled. Names must be exactly `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`.
- An Airtable authentication or "NOT_FOUND"/"INVALID" error : the `AIRTABLE_API_KEY` or `AIRTABLE_BASE_ID` is wrong, or the token was not given access to your base (Part 3.2, step 5), or a **table name** does not match exactly (`Pipeline`, `Companies`, `Job Applications`).
- `Gmail IMAP login failed` : the app password is wrong, has spaces in it, or 2-Step Verification is not on. Redo Part 4 and re-save the `GMAIL_APP_PASSWORD` secret.

**You see a box titled `AIRTABLE SETUP PROBLEM` in the log.** Good. The pipeline caught the problem early and is telling you, in plain words, exactly what to fix. Read the box, do what it says, then re-run it (Actions tab, open the failed run, **Re-run all jobs**). The two most common versions are below.

**"Airtable could not find your base ... Not Found"** (also appears as a `404` error). One of three things, in order of likelihood:
1. Your access token is not connected to your base. Go to https://airtable.com/create/tokens, click your token, and under **Access** make sure your base is listed. If not, click **Add a base**, choose it, then **Save changes**.
2. The `AIRTABLE_BASE_ID` secret is wrong. Open your base in the browser, copy the part of the address that starts with `app`, and update the secret (Part 6).
3. Your token is missing the `schema.bases:read` scope. Add it on the same token page.

**"Unknown field name" / the box lists missing fields** (also appears as a `422` error). A column is missing or misspelled in one of your tables. The box names the exact table and field. Open that table in Airtable and add or rename the column to match exactly. The most common miss is the **Company** field on the **Pipeline** and **Job Applications** tables: it must be of type **Link to another record**, pointing at the **Companies** table (see Parts 2.4 and 2.5). Field names are case-sensitive, so `Company` is not the same as `company`.

**It runs green but writes zero rows, every time.** Usually the filters are too strict, or no alert emails have arrived yet, or the example `TARGET_COMPANIES` are not posting roles that fit. Loosen filters (Part 9) and give the email alerts a day or two.

**A job's data looks half-missing in Airtable** (for example Matched Skills is always blank). A field name in the Pipeline table does not exactly match the list in Part 2.5. Airtable silently drops writes to fields that do not exist. Re-check spelling and capitalization.

**One company always returns nothing** and the log says "HTTP 404. Slug may be wrong." That company likely changed or moved its applicant-tracking system. Find its careers-page URL, read the slug from it (see the note above `TARGET_COMPANIES` in `config.py`), and update or remove that line.

**The daily run stopped happening after a while.** GitHub pauses scheduled jobs after 60 days of no activity in the repo. Make any small edit and commit it, or re-enable the workflow from the Actions tab.

---

## Optional: running it on your own computer

You never need this. The GitHub schedule does everything. But if you ever want to run it manually on your own machine:

1. Install Python 3.12 or newer.
2. Download the project (on GitHub, click the green **Code** button, then **Download ZIP**) and unzip it.
3. Copy the file `.env.example` to a new file named `.env` and fill in your four values.
4. In a terminal, from inside the project folder:
   ```
   python -m venv .venv
   source .venv/bin/activate        # on Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   python -m pipeline.main
   ```

The `.env` file is ignored by Git, so your secrets there never get uploaded.
