"""
run_all.py — Parse logs then launch the dashboard.

Usage:
    python run_all.py                        # logs/ folder, switch_logs.db
    python run_all.py --input ./logs/2026-03-12
    python run_all.py --input ./logs --db my.db --port 8502
    python run_all.py --fix-firewall         # add Windows firewall rule then launch
"""

import argparse
import subprocess
import sys
import os
import socket
import platform


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "YOUR_IP"


def fix_windows_firewall(port: int):
    """Add inbound firewall rule for Streamlit on Windows. Needs admin rights."""
    if platform.system() != "Windows":
        print("[firewall] Not Windows — skipping firewall step.")
        return
    rule_name = f"Streamlit_port_{port}"
    cmd = (
        f'netsh advfirewall firewall add rule '
        f'name="{rule_name}" '
        f'dir=in action=allow protocol=TCP localport={port}'
    )
    print(f"[firewall] Adding Windows Firewall rule for port {port}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[firewall] ✅ Rule added successfully.")
    else:
        print(f"[firewall] ❌ Failed — try running this script as Administrator.")
        print(f"[firewall]    Right-click run_all.py → 'Run as administrator'")
        print(f"[firewall]    Or paste this in an admin CMD/PowerShell:\n")
        print(f"    {cmd}\n")


def is_admin():
    """Check if running with admin rights on Windows."""
    if platform.system() != "Windows":
        return True
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input",        default="./logs")
    p.add_argument("--db",           default="switch_logs.db")
    p.add_argument("--year",         type=int, default=2026)
    p.add_argument("--port",         type=int, default=8501)
    p.add_argument("--parse-only",   action="store_true")
    p.add_argument("--fix-firewall", action="store_true",
                   help="Add Windows Firewall rule to allow LAN access (run as Admin)")
    args = p.parse_args()

    # ── Firewall fix ────────────────────────────────────────────────────────
    if args.fix_firewall:
        if not is_admin():
            print("\n⚠️  Not running as Administrator.")
            print("   Close this and right-click the script → 'Run as administrator'")
            print("   OR open an admin CMD and run:")
            print(f"   python run_all.py --fix-firewall\n")
            # Don't exit — still launch the dashboard for localhost use
        else:
            fix_windows_firewall(args.port)
    elif platform.system() == "Windows":
        # Remind user silently if not passed --fix-firewall
        print("[run_all] TIP: If colleagues can't reach the dashboard, run:")
        print(f"          python run_all.py --fix-firewall  (as Administrator)\n")

    # ── Parser ──────────────────────────────────────────────────────────────
    print(f"[run_all] Parsing {args.input} -> {args.db}")
    ret = subprocess.run(
        [sys.executable, "parse.py",
         "--input", args.input,
         "--db",    args.db,
         "--year",  str(args.year)],
        check=False
    )
    if ret.returncode != 0:
        print("[run_all] Parser exited with errors — check output above.")

    if args.parse_only:
        return

    # ── Dashboard ───────────────────────────────────────────────────────────
    lan_ip = get_lan_ip()
    print(f"\n[run_all] Starting dashboard...")
    print(f"          Your laptop   ->  http://localhost:{args.port}")
    print(f"          Colleagues    ->  http://{lan_ip}:{args.port}")
    print(f"          (Both must be on the same Wi-Fi / LAN)\n")

    env = os.environ.copy()
    env["DB"] = args.db

    result = subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "dashboard.py",
         "--server.address",              "0.0.0.0",
         "--server.port",                 str(args.port),
         "--server.headless",             "true",
         "--server.enableCORS",           "false",
         "--server.enableXsrfProtection", "false",
         "--browser.gatherUsageStats",    "false"],
        env=env
    )
    if result.returncode != 0:
        print("\n[run_all] ERROR: Could not launch Streamlit.")
        print("  Fix: pip install streamlit")
        print(f"  Then retry: python run_all.py")


if __name__ == "__main__":
    main()
