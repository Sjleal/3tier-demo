import os
import time
import atexit
import multiprocessing as mp
from typing import List

_PROCS: List[mp.Process] = []
_RUNNING = False

def _burn_cpu(seconds: int) -> None:
  end = time.monotonic() + seconds
  x = 0
  while time.monotonic() < end:
    # Busy loop CPU-bound
    x = (x * 3 + 1) % 10000019


def _cleanup() -> None:
  global _RUNNING
  for p in list(_PROCS):
    if p.is_alive():
      p.terminate()
      p.join(timeout=1)
  _PROCS.clear()
  _RUNNING = False

atexit.register(_cleanup)


def start_load_test(seconds: int = 30, threads: int = 2) -> None:
  global _RUNNING

  seconds = max(1, min(int(seconds), 600))
  threads = max(1, min(int(threads), 128))

  if _RUNNING:
    return
  _RUNNING = True

  try:
    mp.set_start_method("fork")
  except RuntimeError:
    pass

  cpu_count = os.cpu_count() or 1
  threads = max(threads, cpu_count)

  for _ in range(threads):
    p = mp.Process(target=_burn_cpu, args=(seconds,), daemon=True)
    p.start()
    _PROCS.append(p)

  def _reap():
    global _RUNNING
    for p in list(_PROCS):
      p.join()
    _PROCS.clear()
    _RUNNING = False

  t = mp.Process(target=_reap, daemon=True)
  t.start()
