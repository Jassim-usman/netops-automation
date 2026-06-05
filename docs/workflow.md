# Workflow

## End-to-End Flow

```
[AWX Schedule fires]
       │
       ▼
[collect_logs.yml runs]
  · SSH into each switch in inventory
  · Retrieve syslog output
  · Write to logs/raw/<host>_<timestamp>.log
       │
       ▼
[parse.py runs]
  · Scan logs/raw/ for new files
  · Parse and normalize each line
  · Insert structured records into SQLite
  · Mark files as processed
       │
       ▼
[dashboard.py serves]
  · Queries DB on each user interaction
  · Renders live Plotly panels in Streamlit
  · Sidebar filters applied at query time
```

---

## Scheduled Collection (AWX)

AWX triggers the collection playbook on a defined interval (default: every 15 minutes). Each run:

1. Iterates over all hosts in the inventory group `switches`
2. Executes show/log commands via SSH
3. Appends output to a timestamped file in `logs/raw/`
4. Reports job success/failure back to AWX

Failed hosts are skipped without halting the job. AWX logs each run with full output for post-mortem review.

---

## Manual Run

For ad-hoc use or local development without AWX:

```bash
# Full pipeline: parse logs then serve dashboard
python run-all.py

# Parse only (no dashboard)
python parse.py

# Dashboard only (skip parse, use existing DB)
DB=database/switch_logs.db streamlit run dashboard.py
```

Place raw log files in `logs/raw/` or use the samples in `logs/sample/` for a quick demo.

---

## Log Lifecycle

| Stage | Location | Description |
|---|---|---|
| Raw | `logs/raw/` | Unprocessed syslog output from switches |
| Sample | `logs/sample/` | Static reference logs for testing and demos |
| Parsed | `database/switch_logs.db` | Normalized, queryable event records |

Raw files are not deleted after parsing. Archival or rotation is handled externally (e.g. via logrotate or an AWX cleanup job).

---

## Dashboard Interaction

The Streamlit UI is stateless — every filter change re-queries the DB. Sidebar controls:

- **Date range** — filters events by parsed timestamp
- **Host** — scopes all panels to a single switch or shows all
- **Severity** — toggles which severity levels are included

Panels update independently via Streamlit's reactive model.

---

## Error Handling

- **Parse failures** — malformed lines are logged and skipped; processing continues
- **DB write errors** — surfaced as warnings; the run does not abort
- **AWX job failures** — reported in AWX UI; next scheduled run retries automatically
- **Dashboard DB missing** — Streamlit shows empty state panels with an info message rather than crashing
