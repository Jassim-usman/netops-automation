# Architecture

## System Overview

SwitchWatch is structured as a three-stage pipeline: **collect → parse → visualize**. Each stage is decoupled and can be run independently or orchestrated end-to-end via `run-all.py`.

---

## Component Map

```
┌──────────────┐     SSH/SCP      ┌──────────────────┐
│   Switches   │ ───────────────► │  AWX Job (cron)  │
│  (syslog)    │                  │  collect_logs.yml │
└──────────────┘                  └────────┬─────────┘
                                           │
                                   logs/raw/*.log
                                           │
                                           ▼
                                  ┌─────────────────┐
                                  │    parse.py     │
                                  │                 │
                                  │  · Regex parse  │
                                  │  · Normalize    │
                                  │  · Sev tag      │
                                  │  · DB insert    │
                                  └────────┬────────┘
                                           │
                                   SQLite (switch_logs.db)
                                           │
                                           ▼
                                  ┌─────────────────┐
                                  │  dashboard.py   │
                                  │                 │
                                  │  · Live query   │
                                  │  · Plotly figs  │
                                  │  · Streamlit UI │
                                  └─────────────────┘
```

---

## Layers

### Collection Layer — AWX / Ansible

AWX runs `collect_logs.yml` on a schedule. The playbook SSHes into each switch defined in the inventory, retrieves the current syslog buffer, and writes the output to `logs/raw/` with a timestamped filename.

AWX handles:
- Credential management (SSH keys via AWX vault)
- Job scheduling and retry logic
- Execution logging and failure alerting

### Parse Layer — `parse.py`

The parser reads all files in `logs/raw/`, applies regex normalization to extract structured fields (timestamp, hostname, severity, mnemonic, message), and writes records to SQLite. Duplicate detection prevents re-inserting already-processed entries on repeated runs.

### Storage Layer — SQLite

A single `switch_logs.db` file. Schema is simple by design — one primary events table with indexed columns on `timestamp`, `host`, and `severity`. See [schema.md](../database/schema.md).

### Visualization Layer — `dashboard.py`

Streamlit application that queries the DB live. All charts built with Plotly Graph Objects. The UI is organized into panels: event summary, severity distribution, timeline, top mnemonics, port errors, and login audit. Sidebar provides date-range and host filtering.

---

## Data Flow

```
Raw syslog line
    │
    ▼
Regex extraction → {timestamp, host, facility, severity, mnemonic, message}
    │
    ▼
Severity normalization → SEV_ORDER label (Critical / Error / Warning / ...)
    │
    ▼
Deduplication check (hash or unique constraint)
    │
    ▼
SQLite INSERT → events table
    │
    ▼
Streamlit query → Plotly figure → Browser render
```

---

## Design Decisions

**SQLite over PostgreSQL** — The event volume for a typical switch fleet (< 50 devices) fits comfortably in SQLite. Eliminates a server dependency and simplifies deployment.

**AWX over cron** — AWX provides credential vaulting, audit trails, retry logic, and a UI for operations staff who don't have shell access.

**Streamlit over Flask/FastAPI** — Rapid iteration on the analytics UI without building a separate frontend. Streamlit's component model is sufficient for a NOC dashboard.

**Plotly Graph Objects over Express** — `go` gives precise control over trace styling, axis formatting, and hover templates needed for the dark theme.
