"""
dashboard.py — SwitchWatch Network Switch Log Dashboard  v2
Run:  streamlit run dashboard.py
      DB=switch_logs.db streamlit run dashboard.py
"""

import sqlite3
import os
import subprocess
import sys
from datetime import datetime, date, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="SwitchWatch Analytics",
    page_icon="🖧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DARK UI CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700;800&display=swap');

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="block-container"] {
    background: #0d1117 !important;
    color: #c9d1d9 !important;
    font-family: 'Inter', 'Outfit', sans-serif !important;
}
[data-testid="stMainBlockContainer"] {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}
[data-testid="stSidebar"] {
    background: #161b22 !important;
    border-right: 1px solid #21262d !important;
    min-width: 220px !important;
    max-width: 220px !important;
}
[data-testid="stSidebar"] * {
    color: #8b949e !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.85rem !important;
}
.sb-section {
    font-size: 0.68rem !important; font-weight: 700 !important;
    color: #484f58 !important; text-transform: uppercase !important;
    letter-spacing: 0.08em !important; padding: 4px 0 8px !important;
    border-bottom: 1px solid #21262d !important; margin-bottom: 6px !important;
}
div[data-testid="stSidebar"] div[role="radiogroup"] { gap: 2px !important; }
div[data-testid="stSidebar"] div[role="radiogroup"] label {
    background-color: transparent !important; border: none !important;
    padding: 9px 12px !important; border-radius: 6px !important;
    color: #8b949e !important; font-size: 0.855rem !important;
    font-weight: 500 !important; display: flex !important;
    align-items: center !important; gap: 10px !important;
    cursor: pointer !important; transition: all 0.15s ease !important;
    margin-bottom: 1px !important; width: 100% !important;
}
div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
    background-color: #1c2128 !important; color: #c9d1d9 !important;
}
div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background-color: #1f3358 !important; color: #58a6ff !important;
    font-weight: 600 !important;
}
div[data-testid="stSidebar"] div[role="radiogroup"] label div[class*="-indicator"],
div[data-testid="stSidebar"] div[role="radiogroup"] label svg { display: none !important; }
[data-testid="stWidgetSecondaryLabel"] { display: none !important; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
    background: #1c2128 !important; border: 1px solid #30363d !important;
    border-radius: 6px !important; color: #c9d1d9 !important;
    font-size: 0.82rem !important;
}
[data-testid="stSidebar"] [data-testid="stDateInput"] input {
    background: #1c2128 !important; border: 1px solid #30363d !important;
    border-radius: 6px !important; color: #c9d1d9 !important;
    font-size: 0.82rem !important;
}
[data-testid="stSidebar"] button[kind="primary"] {
    background: #1f6feb !important; border: none !important;
    border-radius: 6px !important; color: #ffffff !important;
    font-size: 0.85rem !important; font-weight: 600 !important;
    padding: 9px 14px !important; transition: all 0.15s ease !important;
    width: 100% !important;
}
[data-testid="stSidebar"] button[kind="primary"]:hover { background: #388bfd !important; }
.qinfo-section { border-top: 1px solid #21262d; margin-top: 16px; padding-top: 14px; }
.qinfo-label-head { font-size: 0.68rem; font-weight: 700; color: #484f58;
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px; }
.qinfo-row { display: flex; justify-content: space-between; align-items: center;
    padding: 6px 0; font-size: 0.8rem; border-bottom: 1px solid #1c2128; }
.qinfo-lbl { color: #6e7681; }
.qinfo-val { color: #c9d1d9; font-weight: 600; }
.dash-header {
    display: flex; align-items: flex-start; justify-content: space-between;
    padding: 0 0 16px; border-bottom: 1px solid #21262d; margin-bottom: 20px;
}
.dash-title-row { display: flex; align-items: center; gap: 14px; }
.dash-icon { font-size: 2rem; color: #58a6ff; line-height: 1; }
.dash-title { font-size: 1.65rem; font-weight: 800; color: #f0f6fc;
    font-family: 'Outfit', sans-serif; letter-spacing: -0.02em; line-height: 1.1; }
.dash-subtitle { font-size: 0.82rem; color: #6e7681; margin-top: 3px; font-weight: 400; }
.dash-updated { font-size: 0.79rem; color: #3fb950; display: flex;
    align-items: center; gap: 6px; font-weight: 500; white-space: nowrap; padding-top: 6px; }
.kpi-card {
    background: #161b22 !important; border: 1px solid #21262d !important;
    border-radius: 10px !important; padding: 16px 18px 0 18px !important;
    height: 148px !important; overflow: hidden !important; position: relative !important;
    transition: border-color 0.15s ease, transform 0.15s ease !important;
}
.kpi-card:hover { border-color: #30363d !important; transform: translateY(-2px) !important; }
.kpi-top-row { display: flex; justify-content: space-between;
    align-items: flex-start; margin-bottom: 6px; }
.kpi-label { font-size: 0.78rem; font-weight: 600; text-transform: none; letter-spacing: 0; }
.kpi-icon { font-size: 1.25rem; opacity: 0.85; }
.kpi-number { font-size: 2.35rem; font-weight: 700; color: #f0f6fc; line-height: 1;
    margin-bottom: 5px; font-family: 'Outfit', sans-serif; }
.kpi-delta { font-size: 0.76rem; font-weight: 600; display: flex; align-items: center; gap: 3px; }
.panel {
    background: #161b22 !important; border: 1px solid #21262d !important;
    border-radius: 10px !important; padding: 18px 20px !important; margin-bottom: 16px !important;
}
.panel-title {
    font-size: 1rem !important; font-weight: 700 !important; color: #f0f6fc !important;
    margin-bottom: 14px !important; font-family: 'Outfit', sans-serif !important;
    letter-spacing: -0.01em !important;
}
.sw-table { width: 100%; border-collapse: collapse; font-size: 0.81rem; }
.sw-table th { color: #6e7681; font-weight: 600; font-size: 0.73rem;
    text-transform: uppercase; letter-spacing: 0.05em; padding: 8px 8px 10px;
    text-align: left; border-bottom: 1px solid #21262d; }
.sw-table td { padding: 9px 8px; color: #c9d1d9; border-bottom: 1px solid #1c2128;
    vertical-align: middle; }
.sw-table tr:last-child td { border-bottom: none; }
.sw-table tr:hover td { background: #1c2128; }
.sw-table .num  { color: #f0f6fc; font-weight: 600; }
.sw-table .info-n { color: #58a6ff; font-weight: 500; }
.sw-table .warn-n { color: #d29922; font-weight: 500; }
.sw-table .err-n  { color: #f85149; font-weight: 500; }
.sw-table .crit-n { color: #bc8cff; font-weight: 700; }
.pbar-wrap { background: #21262d; border-radius: 3px; height: 5px;
    width: 72px; display: inline-block; vertical-align: middle; overflow: hidden; }
.pbar-fill { background: #1f6feb; border-radius: 3px; height: 5px; }
.badge-critical { background: #3d0f0f !important; color: #f85149 !important;
    border: 1px solid #6e100e !important; border-radius: 5px !important;
    padding: 2px 7px !important; font-size: 0.67rem !important; font-weight: 700 !important;
    letter-spacing: 0.04em !important; text-transform: uppercase !important;
    display: inline-block !important; white-space: nowrap !important; }
.badge-good { background: #0d2818 !important; color: #3fb950 !important;
    border: 1px solid #196127 !important; border-radius: 5px !important;
    padding: 2px 7px !important; font-size: 0.67rem !important; font-weight: 700 !important;
    letter-spacing: 0.04em !important; text-transform: uppercase !important;
    display: inline-block !important; white-space: nowrap !important; }
.badge-degraded { background: #2d1f00 !important; color: #d29922 !important;
    border: 1px solid #6e4f00 !important; border-radius: 5px !important;
    padding: 2px 7px !important; font-size: 0.67rem !important; font-weight: 700 !important;
    letter-spacing: 0.04em !important; text-transform: uppercase !important;
    display: inline-block !important; white-space: nowrap !important; }
.view-link { color: #58a6ff; font-size: 0.79rem; font-weight: 500;
    cursor: pointer; text-decoration: none; }
.view-link:hover { color: #79c0ff; text-decoration: underline; }
.footer-bar { text-align: center; font-size: 0.76rem; color: #484f58;
    padding: 16px 0 8px; border-top: 1px solid #21262d; margin-top: 20px; }
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #21262d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #30363d; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stDecoration"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── PLOTLY DARK THEME ─────────────────────────────────────────────────────────
PT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Outfit", color="#6e7681", size=11),
    margin=dict(l=40, r=12, t=16, b=30),
    xaxis=dict(gridcolor="#21262d", linecolor="#21262d",
               tickfont=dict(color="#6e7681", size=10), zeroline=False, showgrid=False),
    yaxis=dict(gridcolor="#21262d", linecolor="rgba(0,0,0,0)",
               tickfont=dict(color="#6e7681", size=10), zeroline=False, showgrid=True),
)

# ── DATABASE ──────────────────────────────────────────────────────────────────
DB = os.environ.get("DB", "switch_logs.db")


def q(sql, params=()):
    """Run SQL → DataFrame; returns empty DataFrame on any error."""
    if not os.path.exists(DB):
        return pd.DataFrame()
    try:
        con = sqlite3.connect(DB, timeout=15, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        df = pd.read_sql_query(sql, con, params=params)
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


def safe_col(df, col, default=None):
    """Return df[col] if it exists, else a Series of `default`."""
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)


# ── LOAD DATA ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_all():
    switches = q("""
        SELECT id, hostname, model, ios_version, serial_number,
               mac_address, uptime_raw, last_restart, restart_reason,
               source_file, parsed_at
        FROM switches
        WHERE id IN (SELECT MAX(id) FROM switches GROUP BY hostname)
        ORDER BY hostname
    """)

    ifaces = q("""
        SELECT s.hostname, i.port, i.description, i.status,
               i.vlan, i.duplex, i.speed, i.media_type,
               COALESCE(i.health, 'HIGH') AS health
        FROM interfaces_status i
        JOIN switches s ON s.id = i.switch_id
        WHERE s.id IN (SELECT MAX(id) FROM switches GROUP BY hostname)
        ORDER BY s.hostname, i.port
    """)

    errors = q("""
        SELECT s.hostname, e.port,
               e.align_err, e.fcs_err, e.xmit_err, e.rcv_err,
               e.undersize, e.out_discards, e.oversize,
               e.single_col, e.multi_col, e.late_col,
               e.excess_col, e.carri_sen, e.runts
        FROM interface_errors e
        JOIN switches s ON s.id = e.switch_id
        WHERE s.id IN (SELECT MAX(id) FROM switches GROUP BY hostname)
    """)

    syslog = q("""
        SELECT s.hostname, ev.raw_timestamp, ev.parsed_ts, ev.facility,
               ev.severity, ev.mnemonic, ev.message
        FROM syslog_events ev
        JOIN switches s ON s.id = ev.switch_id
        WHERE ev.severity <= 6
          AND ev.message IS NOT NULL AND ev.message != ''
        ORDER BY ev.parsed_ts DESC
        LIMIT 5000
    """)

    logins = q("""
        SELECT s.hostname, l.raw_timestamp, l.parsed_ts,
               l.username, l.source, l.local_port, l.event_type
        FROM login_events l
        JOIN switches s ON s.id = l.switch_id
        ORDER BY l.parsed_ts DESC
    """)

    sensors = q("""
        SELECT s.hostname, e.sensor, e.location, e.state,
               e.reading_value, e.reading_unit, e.range_min, e.range_max
        FROM environment_sensors e
        JOIN switches s ON s.id = e.switch_id
        WHERE s.id IN (SELECT MAX(id) FROM switches GROUP BY hostname)
    """)

    fans = q("""
        SELECT s.hostname, f.switch_num, f.fan_num, f.speed, f.state, f.airflow
        FROM fan_status f
        JOIN switches s ON s.id = f.switch_id
        WHERE s.id IN (SELECT MAX(id) FROM switches GROUP BY hostname)
    """)

    psus = q("""
        SELECT s.hostname, p.slot, p.pid, p.serial, p.status,
               p.sys_pwr, p.poe_pwr, p.watts
        FROM power_supplies p
        JOIN switches s ON s.id = p.switch_id
        WHERE s.id IN (SELECT MAX(id) FROM switches GROUP BY hostname)
    """)

    # ── Intelligence tables (v2) ─────────────────────────────────────────────
    health = q("""
        SELECT s.hostname, h.health_score, h.health_label,
               h.err_iface_count, h.critical_syslog, h.failed_logins,
               h.bad_sensors, h.failed_fans, h.failed_psus, h.notes
        FROM switch_health h
        JOIN switches s ON s.id = h.switch_id
        ORDER BY h.health_score ASC
    """)

    syssum = q("""
        SELECT s.hostname, ss.mnemonic, ss.facility, ss.max_severity,
               ss.count, ss.first_seen, ss.last_seen
        FROM syslog_summary ss
        JOIN switches s ON s.id = ss.switch_id
        ORDER BY ss.count DESC
    """)

    anomalies = q("""
        SELECT s.hostname, a.username, a.source, a.fail_count,
               a.anomaly_type, a.detected_at
        FROM login_anomalies a
        JOIN switches s ON s.id = a.switch_id
        ORDER BY a.fail_count DESC
    """)

    return switches, ifaces, errors, syslog, logins, sensors, fans, psus, health, syssum, anomalies


switches, ifaces, errors, syslog, logins, sensors, fans, psus, health_df, syssum, anomalies = load_all()

# ── SEVERITY LABELS ───────────────────────────────────────────────────────────
def add_sev_label(df):
    if df.empty or "severity" not in df.columns:
        out = df.copy(); out["sev_label"] = "Info"; return out
    def _m(v):
        try: v = int(v)
        except: return "Info"
        if v <= 2:   return "Critical"
        elif v == 3: return "Error"
        elif v <= 5: return "Warning"
        else:        return "Info"
    out = df.copy(); out["sev_label"] = out["severity"].apply(_m); return out

syslog = add_sev_label(syslog)
SEV_COLORS = {"Info": "#58a6ff", "Warning": "#d29922", "Error": "#f85149", "Critical": "#bc8cff"}
SEV_ORDER  = ["Info", "Warning", "Error", "Critical"]

# ── NORMALISE TIMESTAMPS ──────────────────────────────────────────────────────
if not syslog.empty and "parsed_ts" in syslog.columns:
    syslog["parsed_ts"] = pd.to_datetime(syslog["parsed_ts"], errors="coerce")
    syslog = syslog.dropna(subset=["parsed_ts"])
    syslog = syslog.sort_values("parsed_ts", ascending=False)

# ── DATE RANGE DEFAULTS ───────────────────────────────────────────────────────
if not syslog.empty and "parsed_ts" in syslog.columns and len(syslog):
    _min = syslog["parsed_ts"].min()
    _max = syslog["parsed_ts"].max()
    default_start = _min.date() if pd.notna(_min) else date.today() - timedelta(days=7)
    default_end   = _max.date() if pd.notna(_max) else date.today()
else:
    default_end   = date.today()
    default_start = default_end - timedelta(days=7)

# ── QUICK STATS ───────────────────────────────────────────────────────────────
total_sw  = len(switches) if not switches.empty else 0
active_sw = 0
if not ifaces.empty and "status" in ifaces.columns and "hostname" in ifaces.columns:
    active_sw = min(total_sw, ifaces[ifaces["status"] == "connected"]["hostname"].nunique())

if not syslog.empty and "parsed_ts" in syslog.columns:
    max_ts     = syslog["parsed_ts"].max()
    events_24h = int((syslog["parsed_ts"] >= max_ts - pd.Timedelta(hours=24)).sum()) if pd.notna(max_ts) else len(syslog)
else:
    events_24h = 0

crit_n   = int((syslog["sev_label"] == "Critical").sum()) if not syslog.empty else 0
events_n = len(syslog)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<div class='sb-section'>Navigation</div>", unsafe_allow_html=True)

    nav_options = ["📊  Overview", "🔌  Switches", "📋  Events", "📈  Analytics",
                   "🛡️  Health", "📄  Reports", "⚙️  Settings"]
    if "current_nav" not in st.session_state:
        st.session_state.current_nav = nav_options[0]
    active_idx = nav_options.index(st.session_state.current_nav) \
        if st.session_state.current_nav in nav_options else 0

    sel_nav = st.radio("nav_", options=nav_options, index=active_idx,
                       label_visibility="collapsed", key="sidebar_nav")
    st.session_state.current_nav = sel_nav

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='sb-section'>Filters</div>", unsafe_allow_html=True)

    st.markdown("<div style='font-size:0.73rem;color:#6e7681;font-weight:600;margin-bottom:3px;'>Date Range</div>",
                unsafe_allow_html=True)
    dr = st.date_input("dr_", value=(default_start, default_end),
                       label_visibility="collapsed", key="dr")
    s_date = dr[0] if isinstance(dr, (list, tuple)) and len(dr) >= 1 else default_start
    e_date = dr[1] if isinstance(dr, (list, tuple)) and len(dr) >= 2 else default_end

    host_list = switches["hostname"].tolist() if not switches.empty else []
    sel_host  = st.selectbox("Switch",     ["All Switches"] + host_list)
    sel_sev   = st.selectbox("Severity",   ["All Severity", "Critical", "Error", "Warning", "Info"])
    etype_opts = (sorted(syslog["facility"].dropna().unique().tolist())
                  if not syslog.empty and "facility" in syslog.columns else [])
    sel_etype = st.selectbox("Event Type", ["All Event Types"] + etype_opts)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.button("🔍  Apply Filters", use_container_width=True, type="primary")

    st.markdown(f"""
    <div class='qinfo-section'>
      <div class='qinfo-label-head'>Quick Info</div>
      <div class='qinfo-row'><span class='qinfo-lbl'>Total Switches</span><span class='qinfo-val'>{total_sw}</span></div>
      <div class='qinfo-row'><span class='qinfo-lbl'>Active Switches</span><span class='qinfo-val'>{active_sw}</span></div>
      <div class='qinfo-row'><span class='qinfo-lbl'>Events (24h)</span><span class='qinfo-val'>{events_24h:,}</span></div>
      <div class='qinfo-row'><span class='qinfo-lbl'>Critical Events</span><span class='qinfo-val'>{crit_n}</span></div>
      <div class='qinfo-row'><span class='qinfo-lbl'>Data Source</span><span class='qinfo-val'>SQLite</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# ── FILTER HELPERS ────────────────────────────────────────────────────────────
f_host  = sel_host  != "All Switches"
f_sev   = sel_sev   != "All Severity"
f_etype = sel_etype != "All Event Types"


def apply_f(df, hcol="hostname", scol="sev_label", tcol="parsed_ts", ecol="facility"):
    out = df.copy()
    if f_host  and hcol in out.columns: out = out[out[hcol] == sel_host]
    if f_sev   and scol in out.columns: out = out[out[scol] == sel_sev]
    if f_etype and ecol in out.columns: out = out[out[ecol] == sel_etype]
    if tcol in out.columns:
        try:
            out[tcol] = pd.to_datetime(out[tcol], errors="coerce")
            out = out[(out[tcol].dt.date >= s_date) & (out[tcol].dt.date <= e_date)]
        except Exception:
            pass
    return out


def filt(df, col="hostname"):
    if f_host and not df.empty and col in df.columns:
        return df[df[col] == sel_host].copy()
    return df.copy()


fs  = apply_f(syslog)
fi  = filt(ifaces)
fe  = filt(errors)
fse = filt(sensors)

# ── MAIN HEADER ───────────────────────────────────────────────────────────────
now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.markdown(f"""
<div class='dash-header'>
  <div>
    <div class='dash-title-row'>
      <span class='dash-icon'>🖧</span>
      <div>
        <div class='dash-title'>Network Switch Log Dashboard</div>
        <div class='dash-subtitle'>Real-time overview of network switch events and alerts</div>
      </div>
    </div>
  </div>
  <div class='dash-updated'>🔄 Last updated: {now_s}</div>
</div>
""", unsafe_allow_html=True)


# ── KPI SPARKLINE ─────────────────────────────────────────────────────────────
def sparkline_svg(vals, color):
    w, h = 280, 44
    if len(vals) < 2:
        return f'<svg viewBox="0 0 {w} {h}" style="width:100%;height:44px;display:block;"></svg>'
    mn, mx = min(vals), max(vals)
    span = mx - mn or 1
    pts = [(int(i * w / (len(vals) - 1)),
            int(h - 2 - (v - mn) / span * (h - 4))) for i, v in enumerate(vals)]
    area_d = f"M {pts[0][0]},{h} " + " ".join(f"L {x},{y}" for x, y in pts) + f" L {pts[-1][0]},{h} Z"
    line_d = f"M {pts[0][0]},{pts[0][1]} " + " ".join(f"L {x},{y}" for x, y in pts[1:])
    gid = f"sg{color.lstrip('#')}"
    return f"""
<svg viewBox="0 0 {w} {h}" style="position:absolute;bottom:0;left:0;width:100%;height:44px;
     pointer-events:none;overflow:hidden;" preserveAspectRatio="none">
  <defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{color}" stop-opacity="0.30"/>
    <stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>
  </linearGradient></defs>
  <path d="{area_d}" fill="url(#{gid})"/>
  <path d="{line_d}" fill="none" stroke="{color}" stroke-width="1.8"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def kpi_card(label, val, label_color, icon, spark_vals, trend_text, positive):
    arrow = "↑" if positive else "↓"
    delta_color = "#3fb950" if positive else "#f85149"
    svg = sparkline_svg(spark_vals, label_color)
    return f"""
<div class="kpi-card">
  <div class="kpi-top-row">
    <span class="kpi-label" style="color:{label_color};">{label}</span>
    <span class="kpi-icon" style="color:{label_color};">{icon}</span>
  </div>
  <div class="kpi-number">{val:,}</div>
  <div class="kpi-delta" style="color:{delta_color};">{arrow} {trend_text}</div>
  {svg}
</div>"""


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if sel_nav == "📊  Overview":

    total_ev = len(fs)
    info_ev  = int((fs["sev_label"] == "Info").sum())     if not fs.empty else 0
    warn_ev  = int((fs["sev_label"] == "Warning").sum())  if not fs.empty else 0
    err_ev   = int((fs["sev_label"] == "Error").sum())    if not fs.empty else 0
    crit_ev  = int((fs["sev_label"] == "Critical").sum()) if not fs.empty else 0

    def daily_counts(label):
        if fs.empty or "parsed_ts" not in fs.columns:
            return [0] * 14
        tmp = fs.copy()
        tmp["parsed_ts"] = pd.to_datetime(tmp["parsed_ts"], errors="coerce")
        tmp["d"] = tmp["parsed_ts"].dt.date
        grp = (tmp.groupby("d").size() if label == "Total"
               else tmp[tmp["sev_label"] == label].groupby("d").size())
        days = pd.date_range(end=e_date, periods=14).date
        return [int(grp.get(d, 0)) for d in days]

    def period_trend(label):
        if fs.empty or "parsed_ts" not in fs.columns:
            return "no prior data", True
        tmp = fs.copy()
        tmp["parsed_ts"] = pd.to_datetime(tmp["parsed_ts"], errors="coerce")
        pivot       = pd.Timestamp(e_date)
        week_start  = pivot - pd.Timedelta(days=6)
        prior_end   = week_start - pd.Timedelta(days=1)
        prior_start = prior_end  - pd.Timedelta(days=6)
        if label == "Total":
            cur_n = int(((tmp["parsed_ts"].dt.date >= week_start.date()) &
                         (tmp["parsed_ts"].dt.date <= pivot.date())).sum())
            pri_n = int(((tmp["parsed_ts"].dt.date >= prior_start.date()) &
                         (tmp["parsed_ts"].dt.date <= prior_end.date())).sum())
        else:
            sub   = tmp[tmp["sev_label"] == label]
            cur_n = int(((sub["parsed_ts"].dt.date >= week_start.date()) &
                         (sub["parsed_ts"].dt.date <= pivot.date())).sum())
            pri_n = int(((sub["parsed_ts"].dt.date >= prior_start.date()) &
                         (sub["parsed_ts"].dt.date <= prior_end.date())).sum())
        if pri_n == 0:
            return "no prior data", cur_n == 0
        pct = (cur_n - pri_n) / pri_n * 100
        return f"{abs(pct):.1f}% vs last 7 days", pct >= 0

    kpis = [
        ("Total Events",    total_ev, "#58a6ff", "📅", daily_counts("Total"),    *period_trend("Total")),
        ("Info Events",     info_ev,  "#3fb950", "ℹ️", daily_counts("Info"),     *period_trend("Info")),
        ("Warning Events",  warn_ev,  "#d29922", "⚠️", daily_counts("Warning"),  *period_trend("Warning")),
        ("Error Events",    err_ev,   "#f85149", "⊗",  daily_counts("Error"),    *period_trend("Error")),
        ("Critical Events", crit_ev,  "#bc8cff", "🛡️", daily_counts("Critical"), *period_trend("Critical")),
    ]

    k_cols = st.columns(5, gap="small")
    for col, (label, val, color, icon, spark_vals, delta_txt, positive) in zip(k_cols, kpis):
        with col:
            st.markdown(kpi_card(label, val, color, icon, spark_vals, delta_txt, positive),
                        unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    c_left, c_right = st.columns([3, 2], gap="small")

    with c_left:
        st.markdown("<div class='panel'><div class='panel-title'>Events Over Time</div>", unsafe_allow_html=True)
        if not fs.empty and "parsed_ts" in fs.columns:
            tmp = fs.copy()
            tmp["parsed_ts"] = pd.to_datetime(tmp["parsed_ts"], errors="coerce")
            tmp["date"] = tmp["parsed_ts"].dt.date
            daily = tmp.groupby(["date", "sev_label"]).size().reset_index(name="count")
            fig_l = go.Figure()
            for sev in SEV_ORDER:
                sub = daily[daily["sev_label"] == sev]
                if sub.empty: continue
                fig_l.add_trace(go.Scatter(
                    x=sub["date"], y=sub["count"], name=sev,
                    mode="lines+markers",
                    line=dict(color=SEV_COLORS[sev], width=2, shape="spline"),
                    marker=dict(size=5, color=SEV_COLORS[sev]),
                    hovertemplate=f"<b>{sev}</b><br>%{{x}}<br>Count: %{{y}}<extra></extra>",
                ))
            fig_l.update_layout(**{k: v for k, v in PT.items() if k not in ("xaxis", "yaxis")},
                height=295, hovermode="x unified",
                legend=dict(orientation="h", x=0, y=1.12, font=dict(size=11, color="#c9d1d9"),
                            bgcolor="rgba(0,0,0,0)", itemsizing="constant"),
                xaxis=dict(**PT["xaxis"], title=None, tickformat="%b %d", tickangle=0),
                yaxis=dict(**PT["yaxis"], title=None))
            st.plotly_chart(fig_l, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No timestamped event data available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c_right:
        st.markdown("<div class='panel'><div class='panel-title'>Events by Severity</div>", unsafe_allow_html=True)
        if not fs.empty and "sev_label" in fs.columns:
            sv = fs["sev_label"].value_counts().reset_index()
            sv.columns = ["sev", "cnt"]
            sv["color"] = sv["sev"].map(SEV_COLORS)
            sv["sev"] = pd.Categorical(sv["sev"], categories=SEV_ORDER, ordered=True)
            sv = sv.sort_values("sev")
            legend_labels = [f"{row['sev']} ({row['cnt']:,})" for _, row in sv.iterrows()]
            fig_p = go.Figure(go.Pie(
                labels=legend_labels, values=sv["cnt"].tolist(), hole=0.60,
                marker=dict(colors=sv["color"].tolist(), line=dict(color="#0d1117", width=2.5)),
                textinfo="percent",
                textfont=dict(color="#f0f6fc", size=11, family="Inter"),
                textposition="inside",
                hovertemplate="<b>%{label}</b><br>%{value:,} events (%{percent})<extra></extra>",
                sort=False,
            ))
            fig_p.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, Outfit", color="#6e7681"),
                margin=dict(l=0, r=0, t=10, b=10), height=295, showlegend=True,
                legend=dict(x=0.70, y=0.5, xanchor="left", yanchor="middle",
                            font=dict(size=11, color="#c9d1d9"), bgcolor="rgba(0,0,0,0)",
                            itemsizing="constant"),
            )
            st.plotly_chart(fig_p, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No data.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    t_left, t_right = st.columns([1, 1], gap="small")

    with t_left:
        st.markdown("<div class='panel'><div class='panel-title'>Top 10 Switches by Events</div>", unsafe_allow_html=True)
        if not fs.empty and "hostname" in fs.columns:
            top = (
                fs.groupby("hostname")
                .agg(
                    Events  =("hostname", "count"),
                    Info    =("sev_label", lambda x: (x == "Info").sum()),
                    Warning =("sev_label", lambda x: (x == "Warning").sum()),
                    Error   =("sev_label", lambda x: (x == "Error").sum()),
                    Critical=("sev_label", lambda x: (x == "Critical").sum()),
                )
                .sort_values("Events", ascending=False).head(10)
                .reset_index().rename(columns={"hostname": "Switch"})
            )
            max_ev    = top["Events"].max() or 1
            rows_html = ""
            for _, r in top.iterrows():
                pct = int(r["Events"] / max_ev * 100)
                rows_html += f"""<tr>
                  <td style='font-weight:600;color:#f0f6fc;'>{r['Switch']}</td>
                  <td><div class='pbar-wrap'><div class='pbar-fill' style='width:{pct}%;'></div></div></td>
                  <td class='num'>{int(r['Events']):,}</td>
                  <td class='info-n'>{int(r['Info']):,}</td>
                  <td class='warn-n'>{int(r['Warning']):,}</td>
                  <td class='err-n'>{int(r['Error']):,}</td>
                  <td class='crit-n'>{int(r['Critical'])}</td>
                </tr>"""
            all_sw = fs["hostname"].nunique()
            st.markdown(f"""
            <table class='sw-table'>
              <thead><tr>
                <th>Switch</th><th></th><th>Events</th>
                <th style='color:#58a6ff;'>Info</th>
                <th style='color:#d29922;'>Warning</th>
                <th style='color:#f85149;'>Error</th>
                <th style='color:#bc8cff;'>Critical</th>
              </tr></thead>
              <tbody>{rows_html}</tbody>
            </table>
            <div style='text-align:center;padding:12px 0 2px;'>
              <span class='view-link'>Showing top 10 of {all_sw} switches</span>
            </div>""", unsafe_allow_html=True)
        else:
            st.info("No switch data for current filters.")
        st.markdown("</div>", unsafe_allow_html=True)

    with t_right:
        st.markdown("<div class='panel'><div class='panel-title'>Recent Critical Events</div>", unsafe_allow_html=True)
        if not fs.empty and "sev_label" in fs.columns:
            crit_df = fs[fs["sev_label"] == "Critical"].copy()
            if not crit_df.empty:
                show_cols  = [c for c in ["parsed_ts", "hostname", "sev_label", "facility", "message"] if c in crit_df.columns]
                crit_show  = crit_df[show_cols].head(10)
                rows_html  = ""
                for _, r in crit_show.iterrows():
                    ts_  = str(r.get("parsed_ts", "—"))[5:19]
                    sw_  = r.get("hostname", "—")
                    et_  = r.get("facility", "—")
                    msg_ = str(r.get("message", "—"))[:42]
                    rows_html += f"""<tr>
                      <td style='font-size:0.77rem;color:#6e7681;white-space:nowrap;'>{ts_}</td>
                      <td style='color:#c9d1d9;font-weight:500;'>{sw_}</td>
                      <td><span class='badge-critical'>Critical</span></td>
                      <td style='color:#c9d1d9;'>{et_}</td>
                      <td style='color:#8b949e;font-size:0.77rem;'>{msg_}</td>
                    </tr>"""
                st.markdown(f"""
                <table class='sw-table'>
                  <thead><tr><th>Time</th><th>Switch</th><th>Severity</th><th>Event Type</th><th>Message</th></tr></thead>
                  <tbody>{rows_html}</tbody>
                </table>
                <div style='text-align:center;padding:12px 0 2px;'>
                  <span class='view-link'>View all critical events</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("<div style='text-align:center;padding:60px 0;color:#3fb950;font-size:0.85rem;font-weight:600;'>✅ No critical events in selected time range</div>",
                            unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f"<div class='footer-bar'>Data collected from {total_sw} network switches &nbsp;|&nbsp; Auto-refresh: 60s</div>",
                unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 2 — SWITCHES
# ══════════════════════════════════════════════════════════════════════════════
elif sel_nav == "🔌  Switches":
    st.markdown("<div class='panel'><div class='panel-title'>Active Switch System Status</div>", unsafe_allow_html=True)
    if not switches.empty:
        dc = [c for c in ["hostname","model","ios_version","serial_number","mac_address",
                           "uptime_raw","last_restart","restart_reason"] if c in switches.columns]
        st.dataframe(switches[dc], use_container_width=True, hide_index=True)
    else:
        st.info("No active switches loaded in database.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='panel-title'>Interface Status &amp; Media Breakdown</div>", unsafe_allow_html=True)
    srch = st.text_input("🔍 Search port, description, or VLAN",
                          placeholder="e.g. Gi1/0/1, trunk, Security…", key="topo_srch")
    df_show = fi.copy()
    if srch:
        df_show = df_show[df_show.apply(lambda r: srch.lower() in str(r).lower(), axis=1)]
    if not df_show.empty:
        def sty_st(v):
            if v == "connected":    return "color:#3fb950;font-weight:600"
            if v == "notconnect":   return "color:#f85149"
            if v == "err-disabled": return "color:#f0883e;font-weight:600"
            return "color:#6e7681"
        def sty_health(v):
            if v == "HIGH":   return "color:#3fb950;font-weight:600"
            if v == "MEDIUM": return "color:#d29922;font-weight:600"
            if v == "LOW":    return "color:#f85149;font-weight:700"
            return "color:#6e7681"
        dc2 = [c for c in ["hostname","port","description","status","vlan",
                            "duplex","speed","media_type","health"] if c in df_show.columns]
        style = df_show[dc2].style
        if "status" in dc2:
            style = style.map(sty_st, subset=["status"])
        if "health" in dc2:
            style = style.map(sty_health, subset=["health"])
        st.dataframe(style, use_container_width=True, height=360, hide_index=True)
        st.caption(f"{len(df_show)} interfaces match filters")
    else:
        st.info("No interfaces match the current filter search.")
    st.markdown("</div>", unsafe_allow_html=True)

    if not fi.empty and "vlan" in fi.columns:
        st.markdown("<div class='panel'><div class='panel-title'>VLAN Breakdown</div>", unsafe_allow_html=True)
        vdf = fi.groupby(["hostname", "vlan"]).size().reset_index(name="ports")
        fig = px.bar(vdf, x="vlan", y="ports", color="hostname",
                     color_discrete_sequence=["#58a6ff","#3fb950","#d29922","#bc8cff","#f0883e"],
                     barmode="group")
        fig.update_layout(**PT, height=260, title=None,
                          legend=dict(font=dict(color="#c9d1d9", size=10), bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 3 — EVENTS
# ══════════════════════════════════════════════════════════════════════════════
elif sel_nav == "📋  Events":
    st.markdown("<div class='panel'><div class='panel-title'>Syslog Event Feed</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1: srch2 = st.text_input("🔍 Search mnemonic / message",
                                    placeholder="e.g. BADSERVERTYPEERROR…", key="sys_srch")
    with c2: sv_f  = st.selectbox("Severity ≤", ["All"] + [str(i) for i in range(1, 8)], key="sv_sel")
    with c3:
        fac_l = ["All"] + (sorted(fs["facility"].dropna().unique().tolist())
                           if not fs.empty and "facility" in fs.columns else [])
        fac_f = st.selectbox("Facility", fac_l, key="fac_sel")

    df_sl = fs.copy()
    if srch2:
        df_sl = df_sl[df_sl.apply(lambda r: srch2.lower() in str(r).lower(), axis=1)]
    if sv_f != "All" and "severity" in df_sl.columns:
        df_sl = df_sl[df_sl["severity"] <= int(sv_f)]
    if fac_f != "All" and "facility" in df_sl.columns:
        df_sl = df_sl[df_sl["facility"] == fac_f]

    SC = {0:"#f85149",1:"#f85149",2:"#f0883e",3:"#d29922",4:"#e3b341",5:"#3fb950",6:"#58a6ff",7:"#a5d6ff"}
    SL = {0:"EMERG",1:"ALERT",2:"CRIT",3:"ERROR",4:"WARN",5:"NOTICE",6:"INFO",7:"DEBUG"}

    if not df_sl.empty:
        for _, row in df_sl.head(80).iterrows():
            try:
                sev = int(row.get("severity", 6))
            except (ValueError, TypeError):
                sev = 6
            sc  = SC.get(sev, "#8b949e")
            sl  = SL.get(sev, str(sev))
            ts_str  = str(row.get("parsed_ts", ""))
            msg_str = str(row.get("message", ""))
            mn_str  = str(row.get("mnemonic", ""))
            hn_str  = str(row.get("hostname", ""))
            st.markdown(f"""
            <div style='background:#161b22;border-left:3px solid {sc};border-radius:0 8px 8px 0;
                        padding:11px 15px;margin-bottom:7px;border:1px solid #21262d;
                        border-left:3px solid {sc};'>
              <div style='display:flex;justify-content:space-between;margin-bottom:4px;'>
                <span style='color:#58a6ff;font-weight:600;font-size:0.74rem;'>{ts_str}</span>
                <span style='background:{sc}18;color:{sc};border:1px solid {sc}44;
                             border-radius:4px;padding:1px 8px;font-size:0.69rem;
                             font-weight:700;font-family:Inter;'>{sl} · {mn_str}</span>
              </div>
              <div style='color:#c9d1d9;font-size:0.83rem;font-family:Inter;'>{msg_str}</div>
              <div style='color:#3fb950;font-size:0.71rem;margin-top:4px;font-weight:600;'>💻 {hn_str}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        ch1, ch2 = st.columns(2)
        with ch1:
            if "mnemonic" in df_sl.columns:
                tm = df_sl["mnemonic"].value_counts().head(8).reset_index()
                tm.columns = ["m", "c"]
                fig = go.Figure(go.Bar(x=tm["c"], y=tm["m"], orientation="h",
                    marker=dict(color="#1f6feb", line=dict(color="#388bfd", width=1)),
                    text=tm["c"], textposition="outside", textfont=dict(color="#c9d1d9", size=10)))
                fig.update_layout(**PT, height=260, title="Top Event Mnemonics",
                                  title_font=dict(color="#c9d1d9", size=12))
                fig.update_layout(yaxis=dict(autorange="reversed", gridcolor="#21262d"))
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        with ch2:
            if "sev_label" in df_sl.columns:
                sv2 = df_sl["sev_label"].value_counts().reset_index()
                sv2.columns = ["s", "c"]
                sv2["col"] = sv2["s"].map(SEV_COLORS)
                fig2 = go.Figure(go.Bar(x=sv2["s"], y=sv2["c"],
                    marker=dict(color=sv2["col"].tolist(), line=dict(color="#0d1117", width=1)),
                    text=sv2["c"], textposition="outside", textfont=dict(color="#c9d1d9", size=11)))
                fig2.update_layout(**PT, height=260, title="Events by Severity",
                                   title_font=dict(color="#c9d1d9", size=12))
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    else:
        st.success("✅ No events match current search or filters.")

    # Syslog frequency summary (new)
    if not syssum.empty:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        fs_sum = filt(syssum) if f_host else syssum
        if not fs_sum.empty:
            st.markdown("<div class='panel-title' style='margin-top:10px;'>Event Frequency Summary</div>",
                        unsafe_allow_html=True)
            dc_ss = [c for c in ["hostname","mnemonic","facility","count","max_severity","first_seen","last_seen"]
                     if c in fs_sum.columns]
            st.dataframe(fs_sum[dc_ss].head(30), use_container_width=True, height=220, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 4 — ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
elif sel_nav == "📈  Analytics":
    st.markdown("<div class='panel'><div class='panel-title'>Interface Error Counter Analysis</div>",
                unsafe_allow_html=True)
    ec_all   = ["align_err","fcs_err","xmit_err","rcv_err","undersize","out_discards","runts"]
    show_nz  = st.checkbox("Show only ports with active errors", value=True)
    de       = fe.copy()
    e_num    = [c for c in ec_all if c in de.columns]

    if show_nz and not de.empty and e_num:
        de = de[de[e_num].sum(axis=1) > 0]

    if not de.empty:
        de["total_errors"] = de[e_num].sum(axis=1) if e_num else 0
        ds = de.sort_values("total_errors", ascending=False)

        c1, c2 = st.columns([3, 2], gap="small")
        with c1:
            dc2 = [c for c in ["hostname","port","total_errors"] + e_num if c in ds.columns]
            st.dataframe(ds[dc2], use_container_width=True, height=340, hide_index=True)
        with c2:
            t10 = ds.head(10)
            if not t10.empty and "port" in t10.columns:
                fig = go.Figure(go.Bar(
                    x=t10["total_errors"], y=t10["port"], orientation="h",
                    marker=dict(
                        color=t10["total_errors"],
                        colorscale=[[0,"#1f6feb"],[0.5,"#d29922"],[1,"#f85149"]],
                        cmin=0, cmax=float(t10["total_errors"].max() or 1),
                    ),
                    text=t10["total_errors"], textposition="outside",
                    textfont=dict(color="#c9d1d9", size=10),
                ))
                fig.update_layout(**PT, height=340, title="Top Ports by Error Count",
                                  title_font=dict(color="#c9d1d9", size=12))
                fig.update_layout(yaxis=dict(autorange="reversed", gridcolor="#21262d"))
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        if e_num:
            tot = de[e_num].sum().reset_index()
            tot.columns = ["type", "count"]
            tot = tot[tot["count"] > 0].sort_values("count", ascending=False)
            if not tot.empty:
                fig2 = go.Figure(go.Bar(x=tot["type"], y=tot["count"],
                    marker=dict(color="#1f6feb", line=dict(color="#388bfd", width=1)),
                    text=tot["count"], textposition="outside",
                    textfont=dict(color="#c9d1d9", size=11)))
                fig2.update_layout(**PT, height=220, title="Error Category Breakdown",
                                   title_font=dict(color="#c9d1d9", size=12))
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    else:
        st.success("✅ Clean health report: No port interface errors detected.")
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 5 — HEALTH  (new intelligence view)
# ══════════════════════════════════════════════════════════════════════════════
elif sel_nav == "🛡️  Health":
    st.markdown("<div class='panel'><div class='panel-title'>Switch Health Scores</div>", unsafe_allow_html=True)

    fh = filt(health_df) if f_host else health_df.copy()

    if not fh.empty:
        # Summary cards
        good_n     = int((fh["health_label"] == "GOOD").sum())     if "health_label" in fh.columns else 0
        degraded_n = int((fh["health_label"] == "DEGRADED").sum()) if "health_label" in fh.columns else 0
        crit_n2    = int((fh["health_label"] == "CRITICAL").sum()) if "health_label" in fh.columns else 0

        sc1, sc2, sc3 = st.columns(3, gap="small")
        for col, label, val, color in [
            (sc1, "✅ GOOD",     good_n,     "#3fb950"),
            (sc2, "⚠️ DEGRADED", degraded_n, "#d29922"),
            (sc3, "🔴 CRITICAL", crit_n2,    "#f85149"),
        ]:
            with col:
                st.markdown(f"""
                <div class='kpi-card' style='height:90px !important;'>
                  <div class='kpi-top-row'>
                    <span class='kpi-label' style='color:{color};'>{label}</span>
                  </div>
                  <div class='kpi-number' style='font-size:2rem;'>{val}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # Per-switch score table
        def badge_health(v):
            if v == "GOOD":     return "<span class='badge-good'>GOOD</span>"
            if v == "DEGRADED": return "<span class='badge-degraded'>DEGRADED</span>"
            return "<span class='badge-critical'>CRITICAL</span>"

        rows_html = ""
        for _, r in fh.sort_values("health_score").iterrows():
            score = int(r.get("health_score", 0))
            bar_c = "#3fb950" if score >= 80 else ("#d29922" if score >= 50 else "#f85149")
            badge = badge_health(str(r.get("health_label", "")))
            rows_html += f"""<tr>
              <td style='font-weight:600;color:#f0f6fc;'>{r.get('hostname','—')}</td>
              <td>{badge}</td>
              <td>
                <div style='display:flex;align-items:center;gap:8px;'>
                  <div style='background:#21262d;border-radius:3px;height:6px;width:80px;overflow:hidden;'>
                    <div style='background:{bar_c};border-radius:3px;height:6px;width:{score}%;'></div>
                  </div>
                  <span style='color:{bar_c};font-weight:700;font-size:0.85rem;'>{score}</span>
                </div>
              </td>
              <td class='err-n'>{int(r.get('err_iface_count',0))}</td>
              <td class='crit-n'>{int(r.get('critical_syslog',0))}</td>
              <td class='warn-n'>{int(r.get('failed_logins',0))}</td>
              <td style='color:#6e7681;font-size:0.77rem;'>{str(r.get('notes',''))[:60]}</td>
            </tr>"""

        st.markdown(f"""
        <table class='sw-table'>
          <thead><tr>
            <th>Switch</th><th>Status</th><th>Score / 100</th>
            <th style='color:#f85149;'>Err Ifaces</th>
            <th style='color:#bc8cff;'>Crit Syslog</th>
            <th style='color:#d29922;'>Login Fails</th>
            <th>Notes</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>""", unsafe_allow_html=True)

        # Score distribution bar chart
        if "health_score" in fh.columns and len(fh) > 1:
            fig = go.Figure(go.Bar(
                x=fh["hostname"], y=fh["health_score"],
                marker=dict(
                    color=fh["health_score"],
                    colorscale=[[0,"#f85149"],[0.5,"#d29922"],[1,"#3fb950"]],
                    cmin=0, cmax=100,
                ),
                text=fh["health_score"], textposition="outside",
                textfont=dict(color="#c9d1d9", size=11),
            ))
            fig.update_layout(**PT, height=220, title=None,
                              yaxis=dict(**PT["yaxis"], range=[0, 110]))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No health data available. Run the parser to generate health scores.")
    st.markdown("</div>", unsafe_allow_html=True)

    # Login anomalies
    fa = filt(anomalies) if f_host else anomalies.copy()
    st.markdown("<div class='panel'><div class='panel-title'>Login Anomaly Detection</div>", unsafe_allow_html=True)
    if not fa.empty:
        dc_a = [c for c in ["hostname","username","source","fail_count","anomaly_type","detected_at"]
                if c in fa.columns]
        def sty_anom(v):
            return "color:#f85149;font-weight:700" if v == "BRUTE_FORCE" else "color:#d29922;font-weight:600"
        style_a = fa[dc_a].style
        if "anomaly_type" in dc_a:
            style_a = style_a.map(sty_anom, subset=["anomaly_type"])
        st.dataframe(style_a, use_container_width=True, hide_index=True)
    else:
        st.success("✅ No login anomalies detected.")
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 6 — REPORTS
# ══════════════════════════════════════════════════════════════════════════════
elif sel_nav == "📄  Reports":
    st.markdown("<div class='panel'><div class='panel-title'>Thermal &amp; Environment Reports</div>",
                unsafe_allow_html=True)
    if not fse.empty:
        if sel_host != "All Switches":
            temp = fse[fse["reading_unit"] == "Celsius"].copy() if "reading_unit" in fse.columns else pd.DataFrame()
            if not temp.empty:
                tc = st.columns(min(len(temp), 4))
                for i, (_, row) in enumerate(temp.iterrows()):
                    val = float(row.get("reading_value") or 0)
                    rm  = float(row.get("range_max") or 125) or 125
                    pct = min(100, val / rm * 100)
                    tc_ = "#3fb950" if pct < 50 else ("#d29922" if pct < 75 else "#f85149")
                    with tc[i % len(tc)]:
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number", value=val,
                            number=dict(suffix="°C", font=dict(color="#f0f6fc", size=24, family="Outfit")),
                            gauge=dict(
                                axis=dict(range=[0, rm], tickfont=dict(size=8, color="#6e7681")),
                                bar=dict(color=tc_, thickness=0.25),
                                bgcolor="#161b22", bordercolor="#21262d",
                                steps=[dict(range=[0, rm*.5], color="#1a2332"),
                                       dict(range=[rm*.5, rm*.75], color="#1f2d1a"),
                                       dict(range=[rm*.75, rm], color="#2d1a1a")],
                                threshold=dict(line=dict(color="#f85149", width=2),
                                               thickness=0.75, value=rm*.9),
                            ),
                            title=dict(text=str(row.get("sensor", "")),
                                       font=dict(color="#6e7681", size=11, family="Outfit")),
                        ))
                        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                                          plot_bgcolor="rgba(0,0,0,0)",
                                          height=180, margin=dict(l=15, r=15, t=30, b=5))
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        dc3 = [c for c in ["hostname","sensor","state","reading_value","reading_unit","range_min","range_max"]
               if c in fse.columns]
        def sty_s(v):
            return "color:#3fb950" if v in ("GOOD","GREEN","OK","NORMAL") else "color:#f85149;font-weight:600"
        style_s = fse[dc3].style
        if "state" in dc3:
            style_s = style_s.map(sty_s, subset=["state"])
        if sel_host == "All Switches":
            st.info("💡 Select a specific Switch in the sidebar to see gauge dials.")
            st.markdown("<div style='font-size:0.85rem;font-weight:600;color:#c9d1d9;margin-bottom:8px;'>Environment Sensors Overview</div>",
                        unsafe_allow_html=True)
        st.dataframe(style_s, use_container_width=True, height=300, hide_index=True)
    else:
        st.info("No environmental sensors data in database.")
    st.markdown("</div>", unsafe_allow_html=True)

    ff = filt(fans)
    if not ff.empty:
        st.markdown("<div class='panel'><div class='panel-title'>Fan Speed &amp; Airflow</div>",
                    unsafe_allow_html=True)
        fc1, fc2 = st.columns(2, gap="small")
        with fc1:
            dc4 = [c for c in ["hostname","fan_num","speed","state","airflow"] if c in ff.columns]
            def sty_fan(v):
                return "color:#3fb950;font-weight:600" if v in ("OK","GOOD") else "color:#f85149;font-weight:700"
            style_fan = ff[dc4].style
            if "state" in dc4:
                style_fan = style_fan.map(sty_fan, subset=["state"])
            st.dataframe(style_fan, use_container_width=True, hide_index=True)
        with fc2:
            if "speed" in ff.columns and "hostname" in ff.columns:
                fig = go.Figure()
                for hn in ff["hostname"].unique()[:6]:
                    sub = ff[ff["hostname"] == hn]
                    fig.add_trace(go.Bar(name=hn, x=sub["fan_num"].astype(str), y=sub["speed"],
                        text=sub["speed"], textposition="outside",
                        textfont=dict(size=10, color="#c9d1d9")))
                fig.update_layout(**PT, height=240, title=None, barmode="group",
                    legend=dict(font=dict(color="#c9d1d9", size=10), bgcolor="rgba(0,0,0,0)"),
                    colorway=["#58a6ff","#3fb950","#d29922","#bc8cff"])
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    fp = filt(psus)
    if not fp.empty:
        st.markdown("<div class='panel'><div class='panel-title'>Power Supply Units (PSU)</div>",
                    unsafe_allow_html=True)
        dc5 = [c for c in ["hostname","slot","pid","serial","status","sys_pwr","poe_pwr","watts"]
               if c in fp.columns]
        def sty_p(v):
            return "color:#3fb950;font-weight:600" if v in ("OK","Good","GOOD") else "color:#f85149;font-weight:600"
        sc5 = [c for c in ["status","sys_pwr","poe_pwr"] if c in dc5]
        style_p = fp[dc5].style
        if sc5:
            style_p = style_p.map(sty_p, subset=sc5)
        st.dataframe(style_p, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    fl = filt(logins)
    st.markdown("<div class='panel'><div class='panel-title'>Authentication &amp; User Session Logins</div>",
                unsafe_allow_html=True)
    if not fl.empty:
        dc6 = [c for c in ["hostname","parsed_ts","username","source","local_port","event_type"]
               if c in fl.columns]
        st.dataframe(fl[dc6], use_container_width=True, height=260, hide_index=True)
        c1, c2 = st.columns(2, gap="small")
        with c1:
            if "username" in fl.columns:
                uc = fl["username"].value_counts().reset_index()
                uc.columns = ["u", "n"]
                fig = go.Figure(go.Bar(x=uc["u"], y=uc["n"],
                    marker=dict(color="#3fb950"),
                    text=uc["n"], textposition="outside",
                    textfont=dict(color="#c9d1d9", size=11)))
                fig.update_layout(**PT, height=240, title="Logins by Username",
                                  title_font=dict(color="#c9d1d9", size=12))
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        with c2:
            if "hostname" in fl.columns:
                hc = fl["hostname"].value_counts().reset_index()
                hc.columns = ["s", "n"]
                fig2 = go.Figure(go.Bar(x=hc["s"], y=hc["n"],
                    marker=dict(color="#58a6ff"),
                    text=hc["n"], textposition="outside",
                    textfont=dict(color="#c9d1d9", size=11)))
                fig2.update_layout(**PT, height=240, title="Logins by Switch Host",
                                   title_font=dict(color="#c9d1d9", size=12))
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No user authentication logins recorded.")
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 7 — SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
elif sel_nav == "⚙️  Settings":
    st.markdown("<div class='panel'><div class='panel-title'>Database Status &amp; System Administration</div>",
                unsafe_allow_html=True)
    st.markdown("Use these settings to clear caches, force a reparse of the `./logs` directory, or inspect the SQLite database.")
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title' style='font-size:0.92rem !important;color:#c9d1d9 !important;'>Administrative Actions</div>",
                unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="small")
    with c1:
        if st.button("🗑️ Clear Cache & Reload", use_container_width=True):
            st.cache_data.clear()
            st.success("Caches cleared. Rerunning…")
            st.rerun()
    with c2:
        if st.button("🚀 Force Reparse Logs Folder", use_container_width=True, type="primary"):
            st.warning("Running parse.py… This may take a few seconds.")
            try:
                for ext_file in [DB, f"{DB}-shm", f"{DB}-wal"]:
                    if os.path.exists(ext_file):
                        os.remove(ext_file)
                res = subprocess.run(
                    [sys.executable, "parse.py", "--input", "./logs", "--db", DB],
                    capture_output=True, text=True,
                )
                if res.returncode == 0:
                    st.success("✅ Database reparsed successfully!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"❌ Failed:\n{res.stderr}")
            except Exception as ex:
                st.error(f"❌ Error: {ex}")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title' style='font-size:0.92rem !important;color:#c9d1d9 !important;'>Database Volume Diagnostics</div>",
                unsafe_allow_html=True)
    if os.path.exists(DB):
        db_sz = os.path.getsize(DB) / (1024 * 1024)
        st.markdown(f"""
* **Database Path**: `{os.path.abspath(DB)}`
* **Database File Size**: `{db_sz:.3f} MB`
* **Recorded Switches**: `{len(switches) if not switches.empty else 0}`
* **Recorded Interfaces**: `{len(ifaces):,}`
* **Recorded Interface Errors**: `{len(errors):,}`
* **Recorded Syslog Events**: `{len(syslog):,}`
* **Recorded Auth Logins**: `{len(logins):,}`
* **Syslog Summary Records**: `{len(syssum):,}`
* **Login Anomalies**: `{len(anomalies):,}`
        """)
    else:
        st.error("SQLite database file not found.")
    st.markdown("</div>", unsafe_allow_html=True)
