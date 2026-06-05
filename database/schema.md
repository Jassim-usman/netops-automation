# Database Schema

**File:** `database/switch_logs.db`
**Engine:** SQLite 3

---

## Tables

### `events`

Primary table. One row per parsed log event.

```sql
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_ts        TEXT,
    parsed_ts     TEXT,
    host          TEXT,
    facility      TEXT,
    severity_num  INTEGER,
    sev_label     TEXT,
    mnemonic      TEXT,
    message       TEXT,
    raw_line      TEXT UNIQUE
);
```

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-incremented primary key |
| `raw_ts` | TEXT | Timestamp string as it appeared in the raw log |
| `parsed_ts` | TEXT | ISO 8601 normalized timestamp (`YYYY-MM-DD HH:MM:SS`) |
| `host` | TEXT | Switch hostname or IP address |
| `facility` | TEXT | Cisco syslog facility (e.g. `SYS`, `LINK`, `ETHPORT`) |
| `severity_num` | INTEGER | Numeric syslog severity (0–7) |
| `sev_label` | TEXT | Human-readable severity label (e.g. `Error`, `Warning`) |
| `mnemonic` | TEXT | Cisco log mnemonic (e.g. `CONFIG_I`, `IF_DOWN`) |
| `message` | TEXT | Full event message body |
| `raw_line` | TEXT | Original unmodified log line — UNIQUE enforces deduplication |

---

## Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_parsed_ts   ON events (parsed_ts);
CREATE INDEX IF NOT EXISTS idx_host        ON events (host);
CREATE INDEX IF NOT EXISTS idx_sev_label   ON events (sev_label);
CREATE INDEX IF NOT EXISTS idx_mnemonic    ON events (mnemonic);
```

Indexes are created on the columns most frequently used in dashboard filter queries.

---

## Common Queries

**Events in a date range:**
```sql
SELECT * FROM events
WHERE parsed_ts BETWEEN '2024-01-01' AND '2024-01-31'
ORDER BY parsed_ts DESC;
```

**Event count by severity:**
```sql
SELECT sev_label, COUNT(*) AS cnt
FROM events
GROUP BY sev_label
ORDER BY cnt DESC;
```

**Top 10 mnemonics:**
```sql
SELECT mnemonic, COUNT(*) AS cnt
FROM events
GROUP BY mnemonic
ORDER BY cnt DESC
LIMIT 10;
```

**Events for a specific host:**
```sql
SELECT * FROM events
WHERE host = 'switch01'
ORDER BY parsed_ts DESC;
```

---

## Notes

- `raw_line` has a UNIQUE constraint — duplicate inserts are silently ignored via `INSERT OR IGNORE`
- `parsed_ts` is stored as TEXT in ISO 8601 format; SQLite's string sort order works correctly for datetime comparisons when this format is used consistently
- No foreign keys or multi-table joins — kept deliberately flat for query simplicity and portability
