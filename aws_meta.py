import os
import time
from typing import Optional, Tuple

import requests


IMDS_BASE = "http://169.254.169.254"
_TIMEOUT = 0.2


def _imds_token() -> Optional[str]:
  try:
    r = requests.put(
        f"{IMDS_BASE}/latest/api/token",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.text
  except Exception:
    return None


def _imds_get(path: str) -> str:
  token = _imds_token()
  headers = {"X-aws-ec2-metadata-token": token} if token else {}
  r = requests.get(f"{IMDS_BASE}{path}", headers=headers, timeout=_TIMEOUT)
  r.raise_for_status()
  return r.text


def get_instance_info() -> dict:
  # Works only on EC2. If not available, returns local placeholders.
  try:
    iid = _imds_get("/latest/meta-data/instance-id")
    az = _imds_get("/latest/meta-data/placement/availability-zone")
    return {"instance_id": iid, "az": az}
  except Exception:
    return {"instance_id": "unknown", "az": os.environ.get("AWS_AZ", "unknown")}


_LAST_CPU: Optional[Tuple[float, int, int]] = None  # (ts, idle, total)


def cpu_percent() -> float:
  """
  Lightweight CPU% using /proc/stat (Linux).
  Returns 0..100.
  """
  global _LAST_CPU
  with open("/proc/stat", "r", encoding="utf-8") as f:
    cpu_line = f.readline().strip().split()
  # cpu user nice system idle iowait irq softirq steal guest guest_nice
  vals = list(map(int, cpu_line[1:]))
  idle = vals[3] + vals[4]  # idle + iowait
  total = sum(vals)

  now = time.time()
  if _LAST_CPU is None:
    _LAST_CPU = (now, idle, total)
    return 0.0

  _, last_idle, last_total = _LAST_CPU
  delta_idle = idle - last_idle
  delta_total = total - last_total
  _LAST_CPU = (now, idle, total)

  if delta_total <= 0:
    return 0.0
  usage = (1.0 - (delta_idle / delta_total)) * 100.0
  return round(max(0.0, min(100.0, usage)), 2)
