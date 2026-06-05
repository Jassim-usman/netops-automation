# AWX Job Template — Configuration Reference

This document describes the AWX job template settings for the `collect_logs.yml` playbook.

---

## Job Template Settings

| Field | Value |
|---|---|
| **Name** | `NetOps - Collect Switch Logs` |
| **Job Type** | Run |
| **Inventory** | `Switch Fleet` _(import from `awx/inventory/hosts.yml`)_ |
| **Project** | `netops-automation` _(linked to this repo)_ |
| **Playbook** | `awx/playbooks/collect_logs.yml` |
| **Credentials** | `Switch SSH Key` _(Machine credential, SSH key type)_ |
| **Verbosity** | `1 (Verbose)` |
| **Forks** | `10` |
| **Timeout** | `300` (seconds) |
| **Enable Concurrent Jobs** | No |
| **Enable Fact Cache** | No |

---

## Extra Variables

Set these in the AWX job template under **Extra Variables**:

```yaml
log_output_dir: logs/raw
log_lines: 500
```

Adjust `log_lines` based on your switch syslog buffer size and collection frequency.

---

## Schedule

Configure a schedule on this job template to run automatically:

| Setting | Value |
|---|---|
| **Name** | `Every 15 Minutes` |
| **Start Date/Time** | _(set to current time)_ |
| **Time Zone** | UTC |
| **Repeat Frequency** | Minute |
| **Every** | 15 |

---

## Notifications

Recommended notification integrations (configure under AWX → Notifications):

| Event | Action |
|---|---|
| Job Failed | Slack / email alert to NOC channel |
| Job Success | Optional — log to audit channel |

---

## Credential Setup

Create a **Machine** credential in AWX:

| Field | Value |
|---|---|
| **Name** | `Switch SSH Key` |
| **Credential Type** | Machine |
| **Username** | `netops` _(or your switch service account)_ |
| **SSH Private Key** | _(paste private key — never commit to repo)_ |
| **Privilege Escalation** | Not required for read-only log collection |

---

## Notes

- Ensure the AWX execution environment has `ansible.netcommon` and `cisco.ios` / `cisco.nxos` collections installed
- The job writes files to `logs/raw/` relative to the project directory on the AWX execution node — confirm the path is accessible and has write permissions
- `serial: 10` in the playbook limits concurrent switch connections to avoid overwhelming devices; adjust in the playbook if needed
