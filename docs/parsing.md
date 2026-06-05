# Log Parsing

## Overview

`parse.py` is responsible for transforming raw, unstructured syslog text into normalized records in SQLite. It handles multi-vendor switch log formats, extracts structured fields via regex, and classifies each event by severity.

---

## Supported Log Formats

### Cisco IOS / IOS-XE

```
*Jan  1 00:01:23.456: %SYS-5-CONFIG_I: Configured from console by vty0 (10.0.0.1)
```

### Cisco NX-OS

```
2024 Jan  1 00:01:23.456 switch %ETHPORT-5-IF_UP: Interface Ethernet1/1 is up
```

### Generic Syslog (RFC 3164)

```
Jan  1 00:01:23 switch01 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down
```

---

## Extracted Fields

| Field | Description | Example |
|---|---|---|
| `raw_ts` | Timestamp string as found in log | `Jan  1 00:01:23.456` |
| `parsed_ts` | Normalized Python datetime | `2024-01-01 00:01:23` |
| `host` | Switch hostname or IP | `switch01` |
| `facility` | Cisco facility code | `SYS`, `ETHPORT`, `LINK` |
| `severity_num` | Numeric syslog severity (0–7) | `5` |
| `sev_label` | Human-readable severity label | `Notice` |
| `mnemonic` | Cisco log mnemonic | `CONFIG_I`, `IF_UP` |
| `message` | Full message body | `Configured from console by...` |
| `raw_line` | Original unmodified log line | _(full string)_ |

---

## Severity Mapping

| Numeric | Label | Color |
|---|---|---|
| 0 | Critical | Red |
| 1 | Critical | Red |
| 2 | Critical | Red |
| 3 | Error | Orange |
| 4 | Warning | Yellow |
| 5 | Notice | Blue |
| 6 | Info | Green |
| 7 | Debug | Grey |

Levels 0–2 are collapsed to `Critical` since syslog severities 0 (Emergency), 1 (Alert), and 2 (Critical) all warrant immediate attention in a NOC context.

---

## Parse Pipeline

```
Read line from raw log
       │
       ▼
Match against primary regex pattern
       │
    match? ──No──► Try fallback pattern
       │                  │
      Yes              match? ──No──► Log as unparseable, skip
       │                 Yes
       ▼                  │
Extract fields ◄──────────┘
       │
       ▼
Normalize timestamp → UTC datetime
       │
       ▼
Map severity_num → sev_label
       │
       ▼
Deduplicate check (raw_line hash vs existing records)
       │
    exists? ──Yes──► Skip
       │
      No
       ▼
INSERT into events table
```

---

## Deduplication

Before inserting, the parser checks whether an identical `raw_line` already exists in the DB. This allows `parse.py` to be run repeatedly against the same `logs/raw/` directory without creating duplicate records — useful for scheduled runs where log files may overlap.

---

## Extending the Parser

To add support for a new log format:

1. Define a new regex pattern that captures the required named groups (`raw_ts`, `host`, `facility`, `severity_num`, `mnemonic`, `message`)
2. Add it to the pattern list in `parse.py` — patterns are tried in order; first match wins
3. If the timestamp format differs, add a corresponding strptime format string to the timestamp normalization function
4. Test against sample logs in `logs/sample/`
