import threading
import time


def _burn_cpu(seconds: int):
    end = time.time() + seconds
    x = 0
    while time.time() < end:
        x = (x * 3 + 1) % 10000019  # busy loop


def start_load_test(seconds: int = 30, threads: int = 2) -> None:
    seconds = max(1, min(seconds, 600))
    threads = max(1, min(threads, 16))

    for _ in range(threads):
        t = threading.Thread(target=_burn_cpu, args=(seconds,), daemon=True)
        t.start()

