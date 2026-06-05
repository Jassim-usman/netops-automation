"""
parse.py — SwitchWatch: Cisco IOS-XE switch log parser (v2 — production-ready)

Usage:
    python parse.py --input ./logs --db switch_logs.db
    python parse.py --input ./logs/2026-03-12 --db switch_logs.db --year 2026
    python parse.py --input ./logs --db switch_logs.db --verbose
"""

import re
import os
import sys
import sqlite3
import argparse
import hashlib
import logging
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("switchwatch.parser")

# ---------------------------------------------------------------------------
# Schema  (original tables preserved; new intelligence tables added)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS switches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname        TEXT NOT NULL,
    model           TEXT,
    ios_version     TEXT,
    serial_number   TEXT,
    mac_address     TEXT,
    uptime_raw      TEXT,
    last_restart    TEXT,
    restart_reason  TEXT,
    source_file     TEXT UNIQUE,
    parsed_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_switches_hostname ON switches(hostname);

CREATE TABLE IF NOT EXISTS interfaces_status (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL REFERENCES switches(id),
    port            TEXT NOT NULL,
    description     TEXT,
    status          TEXT,
    vlan            TEXT,
    duplex          TEXT,
    speed           TEXT,
    media_type      TEXT,
    health          TEXT,
    UNIQUE(switch_id, port)
);
CREATE INDEX IF NOT EXISTS idx_iface_switch ON interfaces_status(switch_id);
CREATE INDEX IF NOT EXISTS idx_iface_port   ON interfaces_status(port);
CREATE INDEX IF NOT EXISTS idx_iface_status ON interfaces_status(status);

CREATE TABLE IF NOT EXISTS interface_errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL REFERENCES switches(id),
    port            TEXT NOT NULL,
    align_err       INTEGER DEFAULT 0,
    fcs_err         INTEGER DEFAULT 0,
    xmit_err        INTEGER DEFAULT 0,
    rcv_err         INTEGER DEFAULT 0,
    undersize       INTEGER DEFAULT 0,
    out_discards    INTEGER DEFAULT 0,
    oversize        INTEGER DEFAULT 0,
    single_col      INTEGER DEFAULT 0,
    multi_col       INTEGER DEFAULT 0,
    late_col        INTEGER DEFAULT 0,
    excess_col      INTEGER DEFAULT 0,
    carri_sen       INTEGER DEFAULT 0,
    runts           INTEGER DEFAULT 0,
    UNIQUE(switch_id, port)
);
CREATE INDEX IF NOT EXISTS idx_errs_switch ON interface_errors(switch_id);
CREATE INDEX IF NOT EXISTS idx_errs_total  ON interface_errors(switch_id, fcs_err, runts);

CREATE TABLE IF NOT EXISTS environment_sensors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL REFERENCES switches(id),
    sensor          TEXT NOT NULL,
    location        TEXT,
    state           TEXT,
    reading_value   REAL,
    reading_unit    TEXT,
    range_min       REAL,
    range_max       REAL,
    UNIQUE(switch_id, sensor, location)
);
CREATE INDEX IF NOT EXISTS idx_env_switch ON environment_sensors(switch_id);
CREATE INDEX IF NOT EXISTS idx_env_state  ON environment_sensors(state);

CREATE TABLE IF NOT EXISTS fan_status (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL REFERENCES switches(id),
    switch_num      TEXT,
    fan_num         TEXT,
    speed           INTEGER,
    state           TEXT,
    airflow         TEXT,
    UNIQUE(switch_id, switch_num, fan_num)
);
CREATE INDEX IF NOT EXISTS idx_fan_switch ON fan_status(switch_id);

CREATE TABLE IF NOT EXISTS power_supplies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL REFERENCES switches(id),
    slot            TEXT,
    pid             TEXT,
    serial          TEXT,
    status          TEXT,
    sys_pwr         TEXT,
    poe_pwr         TEXT,
    watts           INTEGER,
    UNIQUE(switch_id, slot)
);
CREATE INDEX IF NOT EXISTS idx_psu_switch ON power_supplies(switch_id);

CREATE TABLE IF NOT EXISTS syslog_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL REFERENCES switches(id),
    raw_timestamp   TEXT,
    parsed_ts       TEXT,
    facility        TEXT,
    severity        INTEGER,
    mnemonic        TEXT,
    message         TEXT,
    msg_hash        TEXT,
    UNIQUE(switch_id, msg_hash)
);
CREATE INDEX IF NOT EXISTS idx_syslog_switch    ON syslog_events(switch_id);
CREATE INDEX IF NOT EXISTS idx_syslog_ts        ON syslog_events(parsed_ts);
CREATE INDEX IF NOT EXISTS idx_syslog_severity  ON syslog_events(severity);
CREATE INDEX IF NOT EXISTS idx_syslog_mnem      ON syslog_events(mnemonic);
CREATE INDEX IF NOT EXISTS idx_syslog_facility  ON syslog_events(facility);

CREATE TABLE IF NOT EXISTS login_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL REFERENCES switches(id),
    raw_timestamp   TEXT,
    parsed_ts       TEXT,
    username        TEXT,
    source          TEXT,
    local_port      TEXT,
    event_type      TEXT
);
CREATE INDEX IF NOT EXISTS idx_login_switch     ON login_events(switch_id);
CREATE INDEX IF NOT EXISTS idx_login_event_type ON login_events(event_type);
CREATE INDEX IF NOT EXISTS idx_login_user       ON login_events(username);

-- ── Intelligence tables (new) ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS switch_health (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL UNIQUE REFERENCES switches(id),
    health_score    INTEGER,          -- 0-100
    health_label    TEXT,             -- GOOD / DEGRADED / CRITICAL
    err_iface_count INTEGER DEFAULT 0,
    critical_syslog INTEGER DEFAULT 0,
    failed_logins   INTEGER DEFAULT 0,
    bad_sensors     INTEGER DEFAULT 0,
    failed_fans     INTEGER DEFAULT 0,
    failed_psus     INTEGER DEFAULT 0,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_health_switch ON switch_health(switch_id);

CREATE TABLE IF NOT EXISTS syslog_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL REFERENCES switches(id),
    mnemonic        TEXT NOT NULL,
    facility        TEXT,
    max_severity    INTEGER,
    count           INTEGER DEFAULT 1,
    first_seen      TEXT,
    last_seen       TEXT,
    UNIQUE(switch_id, mnemonic)
);
CREATE INDEX IF NOT EXISTS idx_syssum_switch ON syslog_summary(switch_id);
CREATE INDEX IF NOT EXISTS idx_syssum_count  ON syslog_summary(count);

CREATE TABLE IF NOT EXISTS login_anomalies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id       INTEGER NOT NULL REFERENCES switches(id),
    username        TEXT,
    source          TEXT,
    fail_count      INTEGER DEFAULT 0,
    anomaly_type    TEXT,
    detected_at     TEXT,
    UNIQUE(switch_id, username, source)
);
CREATE INDEX IF NOT EXISTS idx_anom_switch ON login_anomalies(switch_id);
"""

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

RE_HOSTNAME_PROMPT = re.compile(
    r'^([A-Za-z0-9][A-Za-z0-9_\-\.]{0,62})(?:#|>)\s*(?:$|\S)'
)
_HOSTNAME_BLACKLIST = frozenset({
    'version', 'model', 'serial', 'base', 'switch', 'port', 'vlan',
    'show', 'interface', 'router', 'hostname', 'cisco',
})

RE_SYSLOG = re.compile(
    r'^\*?(?:\d+:\s*)?'
    r'(?P<ts>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    r'\s+\d{1,2}(?:\s+\d{4})?\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
    r'\s*:?\s*(?:[A-Z]{2,5}:\s+)?'
    r'%(?P<facility>[A-Z][A-Z0-9_\-]+)-(?P<severity>[0-7])'
    r'-(?P<mnemonic>[A-Z0-9_]+):\s*(?P<message>.+)$'
)

RE_IFACE_STATUS = re.compile(
    r'^(?P<port>(?:Gi|GigabitEthernet|Te|TenGigabitEthernet|Fa|FastEthernet'
    r'|Hu|HundredGig|Ap|mgmt)\S+)\s+'
    r'(?:"(?P<desc>[^"]*)")?\s*'
    r'(?P<status>connected|notconnect|disabled|err-disabled)\s+'
    r'(?P<vlan>\S+)\s+'
    r'(?P<duplex>a-full|a-half|full|half|auto|-+)\s+'
    r'(?P<speed>a-\d+|[\d]+|auto|-+)\s+'
    r'(?P<media>.+)$'
)

RE_ENV_SENSOR = re.compile(
    r'^\s{1,10}(?P<sensor>[A-Za-z0-9][\w /\-\(\)]+?)\s{2,}'
    r'(?P<location>\S+)\s{2,}'
    r'(?P<state>[A-Z_]+)\s+'
    r'(?P<value>[\d.]+)\s+'
    r'(?P<unit>\S+)\s*'
    r'(?P<range>[\d. \-]*)$'
)

RE_FAN = re.compile(
    r'^\s*(?P<sw>\d+)\s+(?P<fan>\d+)\s+(?P<speed>\d+)\s+(?P<state>\S+)\s+(?P<airflow>.+)$'
)

RE_PSU = re.compile(
    r'^\s*(?P<slot>\d+[AB]?)\s+(?P<pid>\S+)\s+(?P<serial>\S+)\s+(?P<status>\S+)\s+'
    r'(?P<syspwr>\S+)\s+(?P<poepwr>\S+)\s+(?P<watts>\d+)'
)

RE_ERR_ROW1 = re.compile(
    r'^(?P<port>(?:Gi|Te|Fa|Hu|Ap)\S+)\s+'
    r'(?P<align>\d+)\s+(?P<fcs>\d+)\s+(?P<xmit>\d+)\s+'
    r'(?P<rcv>\d+)\s+(?P<under>\d+)\s+(?P<outdis>\d+)\s*$'
)
RE_ERR_ROW2 = re.compile(
    r'^(?P<port>(?:Gi|Te|Fa|Hu|Ap)\S+)\s+'
    r'(?P<scol>\d+)\s+(?P<mcol>\d+)\s+(?P<lcol>\d+)\s+'
    r'(?P<ecol>\d+)\s+(?P<carri>\d+)\s+(?P<runts>\d+)\s*$'
)
RE_ERR_OVER = re.compile(
    r'^(?P<port>(?:Gi|Te|Fa|Hu|Ap)\S+)\s+(?P<over>\d+)\s*$'
)

RE_VERSION   = re.compile(
    r'Cisco\s+IOS(?:[- ]XE)?\s+Software.*Version\s+([\d.]+(?:\(\d+\))?[a-zA-Z0-9.]*)',
    re.IGNORECASE,
)
RE_VERSION2  = re.compile(r'^Version\s+([\d.]+(?:\(\d+\))?[a-zA-Z0-9.]*)')
RE_MODEL     = re.compile(r'Model\s+(?:Number\s*)?:\s*(\S+)', re.IGNORECASE)
RE_SERIAL    = re.compile(r'System\s+Serial\s+Number\s*:\s*(\S+)', re.IGNORECASE)
RE_MAC       = re.compile(r'Base\s+Ethernet\s+MAC\s+Address\s*:\s*([\da-fA-F:]+)', re.IGNORECASE)
RE_UPTIME    = re.compile(r'uptime is (.+)', re.IGNORECASE)
RE_RESTART_AT  = re.compile(r'System\s+restarted\s+at\s+(.+)', re.IGNORECASE)
RE_RESTART_WHY = re.compile(r'Last\s+reload\s+reason\s*:\s*(.+)', re.IGNORECASE)

RE_LOGIN_SUCCESS = re.compile(
    r'%SEC_LOGIN-\d-LOGIN_SUCCESS:.*\[user:\s*(?P<user>\S+)\]'
    r'.*\[Source:\s*(?P<src>[^\]]+)\]'
    r'(?:.*\[localport:\s*(?P<port>[^\]]+)\])?',
    re.IGNORECASE,
)
RE_LOGIN_FAIL = re.compile(
    r'%SEC_LOGIN-\d-LOGIN_FAILED:.*\[user:\s*(?P<user>\S+)\]'
    r'.*\[Source:\s*(?P<src>[^\]]+)\]'
    r'(?:.*\[localport:\s*(?P<port>[^\]]+)\])?',
    re.IGNORECASE,
)
RE_AAA_FAIL = re.compile(
    r'%AAA-\d-(?:BADAUTH|AUTHEN_FAIL|AUTHOR_FAIL|BADSERVERTYPEERROR):'
    r'.*?\[?user:?\s*(?P<user>\S+)\]?'
    r'(?:.*\[Source:\s*(?P<src>[^\]]+)\])?',
    re.IGNORECASE,
)

MONTH_MAP = {m: i + 1 for i, m in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
)}

# Threshold for "high" error count on a port
ERROR_HIGH_THRESHOLD   = 1000
ERROR_MEDIUM_THRESHOLD = 100

# ---------------------------------------------------------------------------
# Section state constants
# ---------------------------------------------------------------------------

SECTION_NONE       = 0
SECTION_IFACE_STAT = 1
SECTION_ENV        = 2
SECTION_ERR1       = 3
SECTION_SYSLOG     = 4
SECTION_VERSION    = 5

# ---------------------------------------------------------------------------
# Timestamp parsing — multi-format, normalises to ISO
# ---------------------------------------------------------------------------

_TS_PATTERNS = [
    # Mar  2 2026 09:53:16 (with year)
    re.compile(r'(\w{3})\s+(\d{1,2})\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})'),
    # Mar  2 09:53:16  or  Mar  2 09:53:16.481 (no year)
    re.compile(r'(\w{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})'),
    # 2026-03-02T09:53:16  (already ISO-ish)
    re.compile(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})'),
    # 2026/03/02 09:53:16
    re.compile(r'(\d{4})[/\-](\d{2})[/\-](\d{2})\s+(\d{2}):(\d{2}):(\d{2})'),
]


def parse_ts(raw: str, file_year: int = 2026) -> str | None:
    """Convert various timestamp formats to ISO 8601 string. Returns None on failure."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        # Pattern 0: month-name with year
        m = _TS_PATTERNS[0].search(raw)
        if m:
            mon, day, yr, hh, mm, ss = m.groups()
            return datetime(int(yr), MONTH_MAP.get(mon, 1), int(day),
                            int(hh), int(mm), int(ss)).isoformat()
        # Pattern 1: month-name without year
        m = _TS_PATTERNS[1].search(raw)
        if m:
            mon, day, hh, mm, ss = m.groups()
            return datetime(file_year, MONTH_MAP.get(mon, 1), int(day),
                            int(hh), int(mm), int(ss)).isoformat()
        # Pattern 2: ISO-ish  2026-03-02T09:53:16
        m = _TS_PATTERNS[2].search(raw)
        if m:
            yr, mo, day, hh, mm, ss = m.groups()
            return datetime(int(yr), int(mo), int(day),
                            int(hh), int(mm), int(ss)).isoformat()
        # Pattern 3: 2026/03/02 09:53:16
        m = _TS_PATTERNS[3].search(raw)
        if m:
            yr, mo, day, hh, mm, ss = m.groups()
            return datetime(int(yr), int(mo), int(day),
                            int(hh), int(mm), int(ss)).isoformat()
    except (ValueError, AttributeError):
        pass
    return None


def _extract_ts_from_line(stripped: str, file_year: int) -> tuple[str | None, str | None]:
    """Extract raw_ts string and parsed ISO from a line (best effort)."""
    m = re.search(
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        r'\s+(\d{1,2})(?:\s+\d{4})?\s+(\d{2}):(\d{2}):(\d{2})',
        stripped,
    )
    if m:
        raw = m.group(0)
        return raw, parse_ts(raw, file_year)
    return None, None


def _make_msg_hash(hostname: str, raw_ts: str, facility: str,
                   mnemonic: str, message: str) -> str:
    key = f"{hostname}|{raw_ts}|{facility}|{mnemonic}|{message[:80]}"
    return hashlib.md5(key.encode()).hexdigest()  # noqa: S324


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

def detect_section(stripped: str) -> int | None:
    sl = stripped.lower()
    if re.search(r'show interfaces status', sl):
        return SECTION_IFACE_STAT
    if re.search(r'show environment\s*(all|status)?$', sl):
        return SECTION_ENV
    if re.search(r'show logging', sl):
        return SECTION_SYSLOG
    if re.search(r'show interfaces counters errors', sl):
        return SECTION_ERR1
    if re.search(r'show version', sl):
        return SECTION_VERSION
    return None


# ---------------------------------------------------------------------------
# Interface health scoring
# ---------------------------------------------------------------------------

def _iface_health(iface: dict, errors: dict) -> str:
    """Return LOW / MEDIUM / HIGH based on status and error counters."""
    status = iface.get("status", "")
    if status in ("err-disabled", "disabled"):
        return "LOW"
    port = iface.get("port", "")
    e = errors.get(port, {})
    total_errors = sum(
        e.get(k, 0)
        for k in ("fcs_err", "align_err", "rcv_err", "runts",
                  "late_col", "excess_col", "carri_sen")
    )
    if total_errors >= ERROR_HIGH_THRESHOLD:
        return "LOW"
    if total_errors >= ERROR_MEDIUM_THRESHOLD:
        return "MEDIUM"
    if status != "connected":
        return "MEDIUM"
    return "HIGH"


# ---------------------------------------------------------------------------
# Switch health score
# ---------------------------------------------------------------------------

def _compute_health(parsed: dict) -> dict:
    """
    Score 0-100. Deductions:
      - err-disabled / disabled interfaces       -5 each (max -30)
      - critical syslog events (sev 0-2)         -10 each (max -30)
      - failed logins (per unique user)           -5 each (max -15)
      - sensors not GOOD/GREEN                   -5 each (max -20)
      - fans not OK                              -5 each (max -10)
      - PSUs not OK                              -5 each (max -10)
    """
    score = 100
    notes = []

    # Interfaces
    err_ifaces = [i for i in parsed["interfaces"] if i["status"] in ("err-disabled", "disabled")]
    deduct = min(len(err_ifaces) * 5, 30)
    if deduct:
        score -= deduct
        notes.append(f"{len(err_ifaces)} err-disabled/disabled ports")

    # Syslog severity 0-2
    crit_syslog = [e for e in parsed["syslog"] if e["severity"] <= 2]
    deduct = min(len(crit_syslog) * 10, 30)
    if deduct:
        score -= deduct
        notes.append(f"{len(crit_syslog)} critical syslog events")

    # Failed logins
    fail_users = {e["username"] for e in parsed["logins"]
                  if e["event_type"] in ("LOGIN_FAILED", "AAA_FAILURE")}
    deduct = min(len(fail_users) * 5, 15)
    if deduct:
        score -= deduct
        notes.append(f"Login failures from {len(fail_users)} user(s)")

    # Sensors
    bad_sensors = [s for s in parsed["sensors"]
                   if s["state"] not in ("GOOD", "GREEN", "OK", "NORMAL")]
    deduct = min(len(bad_sensors) * 5, 20)
    if deduct:
        score -= deduct
        notes.append(f"{len(bad_sensors)} sensors in non-OK state")

    # Fans
    bad_fans = [f for f in parsed["fans"] if f["state"] not in ("OK", "GOOD")]
    deduct = min(len(bad_fans) * 5, 10)
    if deduct:
        score -= deduct
        notes.append(f"{len(bad_fans)} fans not OK")

    # PSUs
    bad_psus = [p for p in parsed["psus"] if p["status"] not in ("OK", "Good", "GOOD")]
    deduct = min(len(bad_psus) * 5, 10)
    if deduct:
        score -= deduct
        notes.append(f"{len(bad_psus)} PSUs not OK")

    score = max(0, score)
    label = "GOOD" if score >= 80 else ("DEGRADED" if score >= 50 else "CRITICAL")

    return {
        "health_score":    score,
        "health_label":    label,
        "err_iface_count": len(err_ifaces),
        "critical_syslog": len(crit_syslog),
        "failed_logins":   len(fail_users),
        "bad_sensors":     len(bad_sensors),
        "failed_fans":     len(bad_fans),
        "failed_psus":     len(bad_psus),
        "notes":           "; ".join(notes) if notes else "All systems nominal",
    }


def _compute_syslog_summary(parsed: dict) -> list[dict]:
    """Group syslog entries by mnemonic, count frequency."""
    groups: dict[str, dict] = {}
    for ev in parsed["syslog"]:
        mnem = ev["mnemonic"]
        if mnem not in groups:
            groups[mnem] = {
                "mnemonic":     mnem,
                "facility":     ev["facility"],
                "max_severity": ev["severity"],
                "count":        0,
                "first_seen":   ev["parsed_ts"],
                "last_seen":    ev["parsed_ts"],
            }
        g = groups[mnem]
        g["count"] += 1
        g["max_severity"] = min(g["max_severity"], ev["severity"])  # lower = worse
        if ev["parsed_ts"]:
            if g["first_seen"] is None or (ev["parsed_ts"] < g["first_seen"]):
                g["first_seen"] = ev["parsed_ts"]
            if g["last_seen"] is None or (ev["parsed_ts"] > g["last_seen"]):
                g["last_seen"] = ev["parsed_ts"]
    return list(groups.values())


def _compute_login_anomalies(parsed: dict) -> list[dict]:
    """Detect brute-force attempts and repeated AAA failures."""
    anomalies = []
    fail_counter: Counter = Counter()
    source_map: dict[str, str] = {}
    for ev in parsed["logins"]:
        if ev["event_type"] in ("LOGIN_FAILED", "AAA_FAILURE"):
            key = (ev["username"], ev["source"])
            fail_counter[key] += 1
            source_map[key] = ev["source"]

    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    for (user, src), count in fail_counter.items():
        if count >= 3:
            atype = "BRUTE_FORCE" if count >= 10 else "REPEATED_FAILURE"
            anomalies.append({
                "username":    user,
                "source":      src,
                "fail_count":  count,
                "anomaly_type": atype,
                "detected_at": now,
            })
    return anomalies


# ---------------------------------------------------------------------------
# File parser
# ---------------------------------------------------------------------------

def parse_file(filepath: Path, file_year: int = 2026) -> dict:
    """Parse one switch dump file; return structured dict."""
    data: dict = {
        "source_file":    str(filepath),
        "hostname":       None,
        "model":          None,
        "ios_version":    None,
        "serial":         None,
        "mac":            None,
        "uptime":         None,
        "last_restart":   None,
        "restart_reason": None,
        "interfaces":     [],
        "errors":         {},
        "sensors":        [],
        "fans":           [],
        "psus":           [],
        "syslog":         [],
        "logins":         [],
        "_syslog_hashes": set(),
        "_login_dedup":   set(),
    }

    # Read file — replace undecodable bytes rather than crashing
    try:
        raw_text = filepath.read_text(errors="replace")
    except OSError as exc:
        log.error(f"Cannot read {filepath}: {exc}")
        raise

    lines = raw_text.splitlines()
    section       = SECTION_NONE
    err_table     = 1
    in_fan_table  = False
    in_psu_table  = False
    in_sensor_table = False
    parse_errors  = 0

    for lineno, line in enumerate(lines, 1):
        try:
            stripped = line.strip()
            if not stripped:
                continue

            # ── hostname (first prompt line wins) ───────────────────────────
            if data["hostname"] is None:
                m = RE_HOSTNAME_PROMPT.match(stripped)
                if m:
                    candidate = m.group(1)
                    if candidate.lower() not in _HOSTNAME_BLACKLIST:
                        data["hostname"] = candidate

            # ── login events (scan every line) ──────────────────────────────
            _parse_login_line(stripped, data, file_year)

            # ── section change detection ────────────────────────────────────
            new_sec = detect_section(stripped)
            if new_sec is not None:
                section = new_sec
                if section == SECTION_ERR1:
                    err_table = 1
                in_fan_table = in_psu_table = in_sensor_table = False
                continue

            # ── dispatch ────────────────────────────────────────────────────
            if section == SECTION_IFACE_STAT:
                _parse_iface_line(stripped, data)

            elif section == SECTION_ENV:
                _parse_env_line(line, stripped, data, in_fan_table, in_psu_table, in_sensor_table)
                # Update env sub-state
                if re.match(r'^Switch\s+FAN\s+Speed', stripped, re.IGNORECASE):
                    in_fan_table = True; in_psu_table = in_sensor_table = False
                elif re.match(r'^SW\s+(?:\S+\s+)?PID', stripped, re.IGNORECASE):
                    in_psu_table = True; in_fan_table = in_sensor_table = False
                elif re.match(r'Sensor\s+List', stripped, re.IGNORECASE):
                    in_sensor_table = True; in_fan_table = in_psu_table = False
                elif re.match(r'Sensor\s+Location', stripped, re.IGNORECASE):
                    in_sensor_table = True; in_fan_table = in_psu_table = False

            elif section == SECTION_ERR1:
                err_table = _parse_error_line(stripped, data, err_table)

            elif section == SECTION_SYSLOG:
                _parse_syslog_line(stripped, data, file_year)

            elif section == SECTION_VERSION:
                _parse_version_line(stripped, data)

        except Exception as exc:
            parse_errors += 1
            if parse_errors <= 5:
                log.warning(f"  Line {lineno} error [{filepath.name}]: {exc}")
            elif parse_errors == 6:
                log.warning(f"  (Suppressing further line errors for {filepath.name})")

    # Fallback hostname from filename stem
    if not data["hostname"]:
        data["hostname"] = re.sub(r'[^A-Za-z0-9_\-]', '_', filepath.stem)[:32]
        log.warning(f"  No hostname in {filepath.name}, using: {data['hostname']}")

    if parse_errors:
        log.info(f"  Skipped {parse_errors} unparseable lines in {filepath.name}")

    # ── Post-parse: attach interface health ─────────────────────────────────
    for iface in data["interfaces"]:
        iface["health"] = _iface_health(iface, data["errors"])

    return data


# ---------------------------------------------------------------------------
# Section sub-parsers
# ---------------------------------------------------------------------------

def _parse_login_line(stripped: str, data: dict, file_year: int):
    """Scan line for login/AAA events; dedup by (type, user, source, ts)."""
    raw_ts, parsed = _extract_ts_from_line(stripped, file_year)

    for pattern, event_type in [
        (RE_LOGIN_SUCCESS, "LOGIN_SUCCESS"),
        (RE_LOGIN_FAIL,    "LOGIN_FAILED"),
        (RE_AAA_FAIL,      "AAA_FAILURE"),
    ]:
        m = pattern.search(stripped)
        if not m:
            continue
        try:
            user = m.group("user").strip() if "user" in m.groupdict() else "UNKNOWN"
            src  = (m.group("src") or "UNKNOWN").strip() if "src" in m.groupdict() else "UNKNOWN"
            port = (m.group("port") or "").strip() if "port" in m.groupdict() else ""
        except (IndexError, AttributeError):
            continue

        dedup_key = (event_type, user, src, raw_ts or "")
        if dedup_key in data["_login_dedup"]:
            continue
        data["_login_dedup"].add(dedup_key)

        data["logins"].append({
            "raw_ts":     raw_ts,
            "parsed_ts":  parsed,
            "username":   user,
            "source":     src,
            "port":       port,
            "event_type": event_type,
        })


def _parse_iface_line(stripped: str, data: dict):
    m = RE_IFACE_STATUS.match(stripped)
    if not m:
        return
    port = m.group("port")
    existing = {i["port"] for i in data["interfaces"]}
    if port in existing:
        log.debug(f"  Duplicate interface {port} skipped")
        return
    data["interfaces"].append({
        "port":   port,
        "desc":   (m.group("desc") or "").strip(),
        "status": m.group("status").lower(),
        "vlan":   m.group("vlan"),
        "duplex": m.group("duplex"),
        "speed":  m.group("speed"),
        "media":  m.group("media").strip(),
        "health": "HIGH",   # will be updated after parse
    })


def _parse_env_line(line: str, stripped: str, data: dict,
                    in_fan: bool, in_psu: bool, in_sensor: bool):
    if re.match(r'^(---|Switch\s+FAN|SW\s+PID|Sensor\s+List|Sensor\s+Location)', stripped, re.IGNORECASE):
        return

    if in_fan:
        m = RE_FAN.match(stripped)
        if m:
            try:
                data["fans"].append({
                    "switch":  m.group("sw"),
                    "fan":     m.group("fan"),
                    "speed":   int(m.group("speed")),
                    "state":   m.group("state").upper(),
                    "airflow": m.group("airflow").strip(),
                })
            except (ValueError, AttributeError) as e:
                log.debug(f"Fan parse skip: {e}")
        return

    if in_psu:
        m = RE_PSU.match(stripped)
        if m:
            try:
                data["psus"].append({
                    "slot":    m.group("slot"),
                    "pid":     m.group("pid"),
                    "serial":  m.group("serial"),
                    "status":  m.group("status"),
                    "sys_pwr": m.group("syspwr"),
                    "poe_pwr": m.group("poepwr"),
                    "watts":   int(m.group("watts")),
                })
            except (ValueError, AttributeError) as e:
                log.debug(f"PSU parse skip: {e}")
        return

    if in_sensor:
        m = RE_ENV_SENSOR.match(line) or RE_ENV_SENSOR.match(stripped)
        if not m:
            return
        try:
            rng = m.group("range").strip()
            rng_min = rng_max = None
            rm = re.match(r'([\d.]+)\s*[-–]\s*([\d.]+)', rng)
            if rm:
                rng_min, rng_max = float(rm.group(1)), float(rm.group(2))
            val  = float(m.group("value"))
            unit = m.group("unit").strip()
            # Sanity: Celsius out of realistic range
            if unit in ("Celsius", "°C") and not (-50 <= val <= 200):
                log.debug(f"  Implausible temp {val}°C — skipped")
                return
            # Sanity: mV / mA / mW — allow very large values (PSU readouts)
            data["sensors"].append({
                "sensor":   m.group("sensor").strip(),
                "location": m.group("location").strip(),
                "state":    m.group("state").strip().upper(),
                "value":    val,
                "unit":     unit,
                "rng_min":  rng_min,
                "rng_max":  rng_max,
            })
        except (ValueError, AttributeError) as e:
            log.debug(f"Sensor parse skip: {e}")


def _parse_error_line(stripped: str, data: dict, err_table: int) -> int:
    if stripped.startswith('Port') and 'Align-Err' in stripped:
        return 1
    if stripped.startswith('Port') and 'Single-Col' in stripped:
        return 2
    if stripped.startswith('Port') and 'OverSize' in stripped:
        return 3
    if stripped.startswith('---') or not stripped:
        return err_table

    if err_table == 1:
        m = RE_ERR_ROW1.match(stripped)
        if m:
            port = m.group("port")
            data["errors"].setdefault(port, {})
            try:
                data["errors"][port].update({
                    "align_err":    int(m.group("align")),
                    "fcs_err":      int(m.group("fcs")),
                    "xmit_err":     int(m.group("xmit")),
                    "rcv_err":      int(m.group("rcv")),
                    "undersize":    int(m.group("under")),
                    "out_discards": int(m.group("outdis")),
                })
            except ValueError as e:
                log.debug(f"Error row1 parse skip: {e}")
    elif err_table == 2:
        m = RE_ERR_ROW2.match(stripped)
        if m:
            port = m.group("port")
            data["errors"].setdefault(port, {})
            try:
                data["errors"][port].update({
                    "single_col": int(m.group("scol")),
                    "multi_col":  int(m.group("mcol")),
                    "late_col":   int(m.group("lcol")),
                    "excess_col": int(m.group("ecol")),
                    "carri_sen":  int(m.group("carri")),
                    "runts":      int(m.group("runts")),
                })
            except ValueError as e:
                log.debug(f"Error row2 parse skip: {e}")
    elif err_table == 3:
        m = RE_ERR_OVER.match(stripped)
        if m:
            port = m.group("port")
            data["errors"].setdefault(port, {})
            try:
                data["errors"][port]["oversize"] = int(m.group("over"))
            except ValueError as e:
                log.debug(f"Error oversize parse skip: {e}")
    return err_table


def _parse_syslog_line(stripped: str, data: dict, file_year: int):
    m = RE_SYSLOG.match(stripped)
    if not m:
        return
    try:
        facility = m.group("facility").upper()
        severity = int(m.group("severity"))
        mnemonic = m.group("mnemonic").upper()
        message  = m.group("message").strip()
        raw_ts   = m.group("ts")
    except (AttributeError, ValueError):
        return

    if not message:
        return
    if not (0 <= severity <= 7):
        log.debug(f"  Invalid severity {severity} — clamping")
        severity = max(0, min(7, severity))

    parsed = parse_ts(raw_ts, file_year)
    h = _make_msg_hash(data["hostname"] or "", raw_ts or "",
                       facility, mnemonic, message)
    if h in data["_syslog_hashes"]:
        log.debug(f"  Duplicate syslog suppressed: {mnemonic}")
        return
    data["_syslog_hashes"].add(h)

    data["syslog"].append({
        "raw_ts":    raw_ts,
        "parsed_ts": parsed,
        "facility":  facility,
        "severity":  severity,
        "mnemonic":  mnemonic,
        "message":   message,
        "msg_hash":  h,
    })


def _parse_version_line(stripped: str, data: dict):
    if data["ios_version"] is None:
        m = RE_VERSION.search(stripped)
        if m:
            data["ios_version"] = m.group(1)
        else:
            m = RE_VERSION2.match(stripped)
            if m:
                data["ios_version"] = m.group(1)
    if data["model"] is None:
        m = RE_MODEL.search(stripped)
        if m:
            data["model"] = m.group(1)
    if data["serial"] is None:
        m = RE_SERIAL.search(stripped)
        if m:
            data["serial"] = m.group(1)
    if data["mac"] is None:
        m = RE_MAC.search(stripped)
        if m:
            data["mac"] = m.group(1)
    if data["uptime"] is None:
        m = RE_UPTIME.search(stripped)
        if m:
            data["uptime"] = m.group(1).strip()
    if data["last_restart"] is None:
        m = RE_RESTART_AT.search(stripped)
        if m:
            data["last_restart"] = m.group(1).strip()
    if data["restart_reason"] is None:
        m = RE_RESTART_WHY.search(stripped)
        if m:
            data["restart_reason"] = m.group(1).strip()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_parsed(parsed: dict, filepath: Path) -> list[str]:
    issues = []
    if not parsed["hostname"]:
        issues.append("No hostname found")
    if not parsed["ios_version"]:
        issues.append("No IOS version found")
    if not parsed["interfaces"]:
        issues.append("No interface status table found")
    if not parsed["syslog"]:
        issues.append("No syslog entries found")
    err_statuses = {i["status"] for i in parsed["interfaces"]}
    if "err-disabled" in err_statuses and not parsed["errors"]:
        issues.append("err-disabled ports present but no error counters found")
    for s in parsed["sensors"]:
        if s["unit"] in ("Celsius", "°C") and s["value"] > 100:
            issues.append(f"High temp: {s['sensor']} = {s['value']}°C")
    return issues


# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------

# Columns added in v2 that may be missing from existing DBs.
# Format: (table, column, column_definition)
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("interfaces_status", "health", "TEXT"),
    # Add future ALTER TABLE migrations here
]


def init_db(db_path: str):
    con = sqlite3.connect(db_path, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")

    # Create tables / indexes
    for stmt in SCHEMA.strip().split(";"):
        s = stmt.strip()
        if s:
            try:
                con.execute(s)
            except sqlite3.OperationalError as e:
                log.warning(f"Schema stmt skipped ({e}): {s[:60]}")

    # Apply column migrations for existing DBs (safe to re-run; ignored if column exists)
    for table, column, col_def in _MIGRATIONS:
        try:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
            log.info(f"Migration applied: added {table}.{column}")
        except sqlite3.OperationalError:
            pass  # Column already exists — expected on re-runs

    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# DB writer — batch inserts, intelligence tables included
# ---------------------------------------------------------------------------

def write_to_db(db_path: str, parsed: dict):
    con = sqlite3.connect(db_path, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    # ── switches upsert ─────────────────────────────────────────────────────
    cur.execute("""
        INSERT INTO switches
            (hostname, model, ios_version, serial_number, mac_address,
             uptime_raw, last_restart, restart_reason, source_file, parsed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source_file) DO UPDATE SET
            hostname       = excluded.hostname,
            model          = excluded.model,
            ios_version    = excluded.ios_version,
            serial_number  = excluded.serial_number,
            mac_address    = excluded.mac_address,
            uptime_raw     = excluded.uptime_raw,
            last_restart   = excluded.last_restart,
            restart_reason = excluded.restart_reason,
            parsed_at      = excluded.parsed_at
    """, (parsed["hostname"], parsed["model"], parsed["ios_version"],
          parsed["serial"],   parsed["mac"],   parsed["uptime"],
          parsed["last_restart"], parsed["restart_reason"],
          parsed["source_file"],  now))

    sw_id = cur.execute(
        "SELECT id FROM switches WHERE source_file=?", (parsed["source_file"],)
    ).fetchone()[0]

    # Wipe child rows for clean re-parse
    for tbl in ("interfaces_status", "interface_errors", "environment_sensors",
                "fan_status", "power_supplies", "login_events",
                "switch_health", "syslog_summary", "login_anomalies"):
        cur.execute(f"DELETE FROM {tbl} WHERE switch_id=?", (sw_id,))
    # syslog: hash-based dedup — do NOT wipe, let UNIQUE(switch_id, msg_hash) handle it

    # ── interfaces (batch) ───────────────────────────────────────────────────
    cur.executemany("""
        INSERT OR IGNORE INTO interfaces_status
            (switch_id, port, description, status, vlan, duplex, speed, media_type, health)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, [(sw_id, i["port"], i["desc"], i["status"], i["vlan"],
           i["duplex"], i["speed"], i["media"], i["health"])
          for i in parsed["interfaces"]])

    # ── interface errors (batch) ─────────────────────────────────────────────
    cur.executemany("""
        INSERT OR IGNORE INTO interface_errors
            (switch_id, port, align_err, fcs_err, xmit_err, rcv_err,
             undersize, out_discards, oversize,
             single_col, multi_col, late_col, excess_col, carri_sen, runts)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(sw_id, port,
           e.get("align_err", 0), e.get("fcs_err", 0),
           e.get("xmit_err", 0),  e.get("rcv_err", 0),
           e.get("undersize", 0), e.get("out_discards", 0),
           e.get("oversize", 0),  e.get("single_col", 0),
           e.get("multi_col", 0), e.get("late_col", 0),
           e.get("excess_col", 0),e.get("carri_sen", 0),
           e.get("runts", 0))
          for port, e in parsed["errors"].items()])

    # ── sensors (batch) ──────────────────────────────────────────────────────
    cur.executemany("""
        INSERT OR IGNORE INTO environment_sensors
            (switch_id, sensor, location, state, reading_value,
             reading_unit, range_min, range_max)
        VALUES (?,?,?,?,?,?,?,?)
    """, [(sw_id, s["sensor"], s["location"], s["state"],
           s["value"], s["unit"], s["rng_min"], s["rng_max"])
          for s in parsed["sensors"]])

    # ── fans (batch) ─────────────────────────────────────────────────────────
    cur.executemany("""
        INSERT OR IGNORE INTO fan_status
            (switch_id, switch_num, fan_num, speed, state, airflow)
        VALUES (?,?,?,?,?,?)
    """, [(sw_id, f["switch"], f["fan"], f["speed"], f["state"], f["airflow"])
          for f in parsed["fans"]])

    # ── psus (batch) ─────────────────────────────────────────────────────────
    cur.executemany("""
        INSERT OR IGNORE INTO power_supplies
            (switch_id, slot, pid, serial, status, sys_pwr, poe_pwr, watts)
        VALUES (?,?,?,?,?,?,?,?)
    """, [(sw_id, p["slot"], p["pid"], p["serial"], p["status"],
           p["sys_pwr"], p["poe_pwr"], p["watts"])
          for p in parsed["psus"]])

    # ── syslog (batch, hash dedup) ───────────────────────────────────────────
    cur.executemany("""
        INSERT OR IGNORE INTO syslog_events
            (switch_id, raw_timestamp, parsed_ts, facility, severity,
             mnemonic, message, msg_hash)
        VALUES (?,?,?,?,?,?,?,?)
    """, [(sw_id, ev["raw_ts"], ev["parsed_ts"], ev["facility"],
           ev["severity"], ev["mnemonic"], ev["message"], ev["msg_hash"])
          for ev in parsed["syslog"]])

    # ── logins (batch) ───────────────────────────────────────────────────────
    cur.executemany("""
        INSERT INTO login_events
            (switch_id, raw_timestamp, parsed_ts, username, source, local_port, event_type)
        VALUES (?,?,?,?,?,?,?)
    """, [(sw_id, lv["raw_ts"], lv["parsed_ts"], lv["username"],
           lv["source"], lv["port"], lv["event_type"])
          for lv in parsed["logins"]])

    # ── intelligence: switch health ──────────────────────────────────────────
    h = _compute_health(parsed)
    cur.execute("""
        INSERT OR REPLACE INTO switch_health
            (switch_id, health_score, health_label, err_iface_count,
             critical_syslog, failed_logins, bad_sensors, failed_fans, failed_psus, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (sw_id, h["health_score"], h["health_label"], h["err_iface_count"],
          h["critical_syslog"], h["failed_logins"], h["bad_sensors"],
          h["failed_fans"], h["failed_psus"], h["notes"]))

    # ── intelligence: syslog summary ─────────────────────────────────────────
    summaries = _compute_syslog_summary(parsed)
    cur.executemany("""
        INSERT OR IGNORE INTO syslog_summary
            (switch_id, mnemonic, facility, max_severity, count, first_seen, last_seen)
        VALUES (?,?,?,?,?,?,?)
    """, [(sw_id, s["mnemonic"], s["facility"], s["max_severity"],
           s["count"], s["first_seen"], s["last_seen"])
          for s in summaries])

    # ── intelligence: login anomalies ────────────────────────────────────────
    anomalies = _compute_login_anomalies(parsed)
    cur.executemany("""
        INSERT OR IGNORE INTO login_anomalies
            (switch_id, username, source, fail_count, anomaly_type, detected_at)
        VALUES (?,?,?,?,?,?)
    """, [(sw_id, a["username"], a["source"], a["fail_count"],
           a["anomaly_type"], a["detected_at"])
          for a in anomalies])

    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def collect_files(input_path: str) -> list[Path]:
    p = Path(input_path)
    if p.is_file():
        return [p]
    files: list[Path] = []
    for ext in ("*.txt", "*.log"):
        files.extend(p.rglob(ext))
    return sorted(files)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="SwitchWatch — Cisco IOS-XE log parser v2")
    ap.add_argument("--input",   default="./logs",         help="Folder or single file")
    ap.add_argument("--db",      default="switch_logs.db", help="SQLite DB path")
    ap.add_argument("--year",    type=int, default=2026,   help="Fallback year for timestamps")
    ap.add_argument("--verbose", action="store_true",      help="DEBUG logging")
    args = ap.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    init_db(args.db)
    log.info(f"DB ready: {args.db}")

    files = collect_files(args.input)
    if not files:
        log.warning(f"No .txt/.log files found under {args.input}")
        sys.exit(0)

    total_ok = total_warn = total_fail = 0

    for f in files:
        log.info(f"Parsing {f}")
        try:
            parsed   = parse_file(f, file_year=args.year)
            warnings = validate_parsed(parsed, f)
            for w in warnings:
                log.warning(f"  Validation: {w}")
            if warnings:
                total_warn += 1

            write_to_db(args.db, parsed)
            total_ok += 1

            h = _compute_health(parsed)
            log.info(
                f"  ✓ {parsed['hostname']:25s}  "
                f"ifaces={len(parsed['interfaces']):3d}  "
                f"errs={len(parsed['errors']):3d}  "
                f"syslog={len(parsed['syslog']):4d}  "
                f"logins={len(parsed['logins']):3d}  "
                f"health={h['health_score']:3d} ({h['health_label']})"
            )
        except Exception as e:
            total_fail += 1
            log.error(f"  ✗ FAILED {f}: {e}", exc_info=args.verbose)

    log.info(f"Done — {total_ok} OK, {total_warn} warnings, {total_fail} failed.")


if __name__ == "__main__":
    main()
