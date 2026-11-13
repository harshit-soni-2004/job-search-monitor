# Python Job-Search Monitor

A daily automated monitor that checks company career portals and official Applicant Tracking System (ATS) APIs for job openings matching your custom criteria, automatically updating an Excel workbook with new postings while **strictly preserving all your personal notes, application statuses, and custom columns**.

---

## Key Features

- **Non-Destructive Excel Sync**:
  - Automatically deduplicates postings using their canonical job URLs.
  - Updates `Last-Checked Date` for active listings.
  - **Never** overwrites or clears your `Status` (e.g., "Applied", "Interviewing", "Offer") or `Notes`.
  - Safely maintains any custom columns you add (e.g., `Salary`, `Referral Contact`).
- **Official ATS API & Feed Priority**:
  - Directly queries public, rate-limited JSON APIs for platforms including:
    - **Greenhouse** (`boards-api.greenhouse.io`)
    - **Lever** (`api.lever.co`)
    - **Ashby** (`api.ashbyhq.com`)
    - **SmartRecruiters** (`api.smartrecruiters.com`)
    - **Workable** (`apply.workable.com`)
  - Semantic **Schema.org `JobPosting` JSON-LD** extraction for modern custom career portals.
  - Public HTML parsing fallback for standard career pages.
- **Polite & Safe Web Access**:
  - Only accesses publicly accessible data.
  - Automatically identifies authentication walls, CAPTCHAs, or anti-bot challenge pages and skips them gracefully with clear log warnings.
- **Auditing & Daily Summaries**:
  - Outputs a clean daily summary table to the console.
  - Stores dated logs in `logs/job_monitor_YYYY-MM-DD.log`.
  - Appends persistent run summaries to `logs/daily_summaries.log`.
- **Configurable Scheduling**:
  - Configurable run times via `config.yaml`.
  - Ready-to-use launch scripts for **Windows Task Scheduler invoking WSL** (`run_wsl.sh`, `run_wsl.bat`) and native Windows (`run_windows.bat`).
- **Zero Secrets Policy**:
  - Requires no API keys or logins; all monitored feeds are public.
  - Workbook, configuration, and log outputs remain completely credential-free.

---

## Excel Workbook Structure (`job_search.xlsx`)

The monitor expects (or generates via `--init-template`) two styled sheets:

### 1. `Sources` Sheet
Define the companies you want to monitor:

| Column Name | Description | Example |
| :--- | :--- | :--- |
| **Company Name** | Name of the organization | `GitLab` |
| **Careers URL** | URL to career portal or ATS board | `https://boards.greenhouse.io/gitlab` |
| **Target Titles** | Comma-separated job title patterns | `Backend Engineer, Software Engineer, Python` |
| **Location Preferences** | Comma-separated locations or 'Remote' | `Remote, US, New York` |
| **Experience Range** | Experience level filter (optional) | `Senior, Intermediate` |
| **Include Keywords** | Required/desired keywords in title or description | `Python, FastAPI, Kubernetes` |
| **Exclude Keywords** | Disqualifying keywords (immediate rejection) | `Intern, Director, Junior, Clearance` |
| **Active** | `Yes` to monitor; `No` to temporarily pause | `Yes` |

### 2. `Matches` Sheet
Where matching jobs are logged and tracked:

| Column Name | Behavior & Guarantees |
| :--- | :--- |
| **Company** | Organization name from source |
| **Job Title** | Title of the position |
| **Location** | Listed location / Remote status |
| **Job URL** | Unique link (used for deduplication) |
| **Posted Date** | Date job was published or updated (if available) |
| **Matched Criteria** | Audit trail of matched criteria (e.g. `Title: Backend; Location: Remote; Keywords: Python`) |
| **First-Seen Date** | Date the monitor first discovered this listing |
| **Last-Checked Date** | Updated on every run as long as the listing remains active |
| **Status** | Defaults to `New`. **Preserved forever** when you change it to `Applied`, `Interviewing`, `Archived`, etc. |
| **Notes** | Blank for new listings. **Preserved forever** when you write custom notes. |

---

## Quickstart

### 1. Installation

From the `jobSearch` directory:

```bash
# Optional: Create a virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# or: source venv/bin/activate  # Linux/WSL

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize Workbook Template

```bash
python main.py --init-template
```
This generates `job_search.xlsx` pre-loaded with the verified 69-company India early-career watchlist (Priority A & B) and formatted headers.

### 3. Run a Monitoring Check

```bash
python main.py --once
```

Example Daily Summary Output:
```text
============================== DAILY JOB SEARCH SUMMARY ==============================
Date / Time:       2026-11-13 16:28:42 (Duration: 8.7s)
Workbook:          job_search.xlsx
Sources Checked:   3 active (3 succeeded, 0 failed/restricted)
Listings Scanned:  459
New Matches:       +25 added
Existing Matches:  0 refreshed (user notes/status untouched)
--------------------------------------------------------------------------------------
COMPANY DETAILS:
  [OK]         GitLab               | Found: 254 | Matched:  17
  [OK]         Discord              | Found:  25 | Matched:   4
  [OK]         Ramp                 | Found: 180 | Matched:   4
======================================================================================
```

---

## Configuration (`config.yaml`)

Edit `config.yaml` to adjust settings:

```yaml
# Path to the Excel workbook
workbook_path: "job_search.xlsx"

# Daily run time (HH:MM in 24h format) for internal scheduler mode (--schedule)
schedule_time: "09:00"

# Polite crawler settings
request_timeout: 15        # Seconds per request
rate_limit_delay: 1.0      # Seconds between consecutive requests
user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (JobSearchMonitor/1.0; Public Careers Checker)"

# Logging
log_level: "INFO"          # DEBUG, INFO, WARNING, ERROR
log_dir: "logs"
save_daily_summary_log: true
```

---

## CLI Options

```bash
# Run one check immediately and exit
python main.py --once

# Run continuous scheduler (triggers daily at schedule_time from config.yaml)
python main.py --schedule

# Use a custom workbook or config file
python main.py --workbook "D:/MyJobs/search.xlsx" --config "my_config.yaml"

# Test a single careers URL without modifying Excel
python main.py --test-source "https://boards.greenhouse.io/gitlab"
```

---

## Scheduling via Windows Task Scheduler into WSL

This setup allows Windows Task Scheduler to wake or run daily, execute the monitor inside your Linux environment (WSL), and update the shared Excel workbook on your Windows drive.

### Path Mapping in WSL
Windows path:
`C:\Users\ihars\Desktop\Workspace\jobSearch`
Translates in WSL to:
`/mnt/c/Users/ihars/Desktop/Workspace/jobSearch`

---

### Step 1: Prepare WSL Environment
Open WSL (Ubuntu or your installed distribution) and ensure Python 3 and dependencies are installed:

```bash
# 1. Open WSL terminal
wsl

# 2. Update and ensure python3 & pip are installed
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# 3. Navigate to the project directory
cd /mnt/c/Users/ihars/Desktop/Workspace/jobSearch

# 4. Make runner script executable
chmod +x run_wsl.sh

# 5. Create a virtual environment inside the folder (optional but recommended)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. Test run directly from WSL
./run_wsl.sh
```

---

### Step 2: Schedule via Windows Command Line (`schtasks`)

Open **PowerShell** or **Command Prompt** (as Administrator if you want to run whether logged on or not) and run:

```powershell
schtasks /create /tn "JobSearchMonitor_WSL" /tr "wsl.exe bash -c 'cd /mnt/c/Users/ihars/Desktop/Workspace/jobSearch && ./run_wsl.sh'" /sc daily /st 09:00 /f
```

*Note: Replace `09:00` with your desired daily run time.*

---

### Step 3: Schedule via Windows Task Scheduler GUI (Alternative)

1. Press `Win + R`, type `taskschd.msc`, and press **Enter**.
2. In the right pane, click **Create Basic Task...** (or **Create Task...**).
3. **Name**: `Job Search Monitor (WSL)`.
4. **Trigger**: Select **Daily**, click Next, set **Start Time** (e.g. `09:00:00 AM`), recur every `1` day.
5. **Action**: Select **Start a program**.
6. **Program/script**:
   ```
   wsl.exe
   ```
7. **Add arguments (optional)**:
   ```
   bash -c "cd /mnt/c/Users/ihars/Desktop/Workspace/jobSearch && ./run_wsl.sh"
   ```
8. **Start in (optional)**: Leave blank or set `C:\Users\ihars\Desktop\Workspace\jobSearch`.
9. Click **Finish**.

> **Tip**: You can also point the Program/script directly to `C:\Users\ihars\Desktop\Workspace\jobSearch\run_wsl.bat`, which invokes WSL with the same parameters.

---

## Native Windows Task Scheduler (Without WSL)

If you prefer to run directly in Windows without WSL:

```powershell
schtasks /create /tn "JobSearchMonitor_Windows" /tr "C:\Users\ihars\Desktop\Workspace\jobSearch\run_windows.bat" /sc daily /st 09:00 /f
```

---

## Safety & Secrets

- **No Passwords or Secrets Required**: The monitor relies solely on public feeds and ATS endpoints.
- **Anti-Bot Protection Compliance**: Does not bypass CAPTCHAs, bot challenges, or logins. If a site blocks programmatic access, it logs a polite warning and continues monitoring the remaining companies without aborting.
- **Log Hygiene**: Workbook data and logs contain only company names, job titles, and public career links.

