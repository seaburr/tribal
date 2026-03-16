"""
Load test for Tribal API.
Targets ~50 RPS with a mix of:
  - 40% POST /api/resources/        (create)
  - 30% PUT  /api/resources/{id}    (edit)
  - 30% GET  /admin/audit-log       (audit log)

Usage:
    python3 loadtest.py [--rps 50] [--duration 30]
"""

import argparse
import asyncio
import random
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field

import httpx

BASE = "http://localhost:8000"
API_KEY = "tribal_sk_26990890ab9858308cd8bc290d880437ca91f518d8720953b8512e5975e58d16"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

RESOURCE_NAMES = ["SSL Cert", "Deploy Key", "GitHub PAT", "DB Password", "S3 Access Key", "CI Token", "GPG Key"]
RESOURCE_TYPES = ["Certificate", "API Key", "SSH Key", "Other"]
DRIS = ["alice@example.com", "bob@example.com", "carol@example.com"]
PURPOSES = ["Production auth", "CI/CD pipeline", "Data backup", "Internal tooling"]


@dataclass
class Stats:
    latencies: list[float] = field(default_factory=list)
    status_counts: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    errors: int = 0
    start: float = field(default_factory=time.monotonic)

    def record(self, latency_ms: float, status: int):
        self.latencies.append(latency_ms)
        self.status_counts[status] += 1

    def record_error(self):
        self.errors += 1

    def report(self, label: str):
        n = len(self.latencies)
        if not n:
            print(f"  {label}: no data")
            return
        s = sorted(self.latencies)
        print(f"  {label} ({n} reqs):")
        print(f"    success/error: {sum(c for k,c in self.status_counts.items() if k < 400)}/{self.errors + sum(c for k,c in self.status_counts.items() if k >= 400)}")
        print(f"    status codes:  {dict(sorted(self.status_counts.items()))}")
        print(f"    latency (ms):  min={s[0]:.0f}  p50={s[n//2]:.0f}  p90={s[int(n*.9)]:.0f}  p99={s[int(n*.99)]:.0f}  max={s[-1]:.0f}")
        if n > 1:
            print(f"    mean±stdev:    {statistics.mean(s):.0f}±{statistics.stdev(s):.0f}")


# Shared state: IDs of created resources so edit requests have something to target
created_ids: list[int] = []
created_ids_lock = asyncio.Lock()


async def do_create(client: httpx.AsyncClient, stats: Stats):
    payload = {
        "name": f"{random.choice(RESOURCE_NAMES)} {random.randint(1000, 9999)}",
        "dri": random.choice(DRIS),
        "type": random.choice(RESOURCE_TYPES),
        "expiration_date": f"20{random.randint(25,27):02d}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        "purpose": random.choice(PURPOSES),
        "generation_instructions": "Rotate via internal tooling.",
        "slack_webhook": "",
    }
    t0 = time.monotonic()
    try:
        r = await client.post(f"{BASE}/api/resources/", json=payload, headers=HEADERS)
        stats.record((time.monotonic() - t0) * 1000, r.status_code)
        if r.status_code == 201:
            rid = r.json().get("id")
            if rid:
                async with created_ids_lock:
                    created_ids.append(rid)
    except Exception:
        stats.record_error()


async def do_edit(client: httpx.AsyncClient, stats: Stats):
    async with created_ids_lock:
        if not created_ids:
            return
        rid = random.choice(created_ids)

    payload = {
        "purpose": random.choice(PURPOSES),
        "expiration_date": f"20{random.randint(25,27):02d}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
    }
    t0 = time.monotonic()
    try:
        r = await client.put(f"{BASE}/api/resources/{rid}", json=payload, headers=HEADERS)
        stats.record((time.monotonic() - t0) * 1000, r.status_code)
    except Exception:
        stats.record_error()


async def do_audit(client: httpx.AsyncClient, stats: Stats):
    offset = random.randint(0, 10) * 25
    t0 = time.monotonic()
    try:
        r = await client.get(f"{BASE}/admin/audit-log", params={"limit": 25, "offset": offset}, headers=HEADERS)
        stats.record((time.monotonic() - t0) * 1000, r.status_code)
    except Exception:
        stats.record_error()


# Weighted request mix: 40% create, 30% edit, 30% audit
TASKS = [do_create] * 40 + [do_edit] * 30 + [do_audit] * 30


async def worker(client: httpx.AsyncClient, queue: asyncio.Queue,
                 create_stats: Stats, edit_stats: Stats, audit_stats: Stats):
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break
        fn, t_scheduled = item
        # Sleep until scheduled time (throttle to target RPS)
        wait = t_scheduled - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)

        stat_map = {do_create: create_stats, do_edit: edit_stats, do_audit: audit_stats}
        await fn(client, stat_map[fn])
        queue.task_done()


async def run(rps: int, duration: int):
    print(f"\nLoad test: {rps} RPS for {duration}s — mix: 40% create / 30% edit / 30% audit\n")

    create_stats = Stats()
    edit_stats = Stats()
    audit_stats = Stats()

    total_requests = rps * duration
    interval = 1.0 / rps

    queue: asyncio.Queue = asyncio.Queue()

    # Pre-seed queue with scheduled request times
    t0 = time.monotonic() + 0.2  # small warmup buffer
    for i in range(total_requests):
        fn = random.choice(TASKS)
        t_scheduled = t0 + i * interval
        queue.put_nowait((fn, t_scheduled))

    # Poison pills to stop workers
    n_workers = min(rps * 2, 200)  # concurrency ceiling
    for _ in range(n_workers):
        queue.put_nowait(None)

    limits = httpx.Limits(max_connections=n_workers, max_keepalive_connections=n_workers)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        wall_start = time.monotonic()

        # Print live throughput every 5 seconds
        async def progress():
            prev = 0
            for tick in range(duration // 5):
                await asyncio.sleep(5)
                done = len(create_stats.latencies) + len(edit_stats.latencies) + len(audit_stats.latencies)
                elapsed = time.monotonic() - wall_start
                actual_rps = (done - prev) / 5
                prev = done
                pct = done / total_requests * 100
                print(f"  [{elapsed:5.1f}s] {done}/{total_requests} reqs ({pct:.0f}%) — {actual_rps:.1f} RPS actual")

        workers = [asyncio.create_task(worker(client, queue, create_stats, edit_stats, audit_stats))
                   for _ in range(n_workers)]
        progress_task = asyncio.create_task(progress())

        await queue.join()
        progress_task.cancel()
        for w in workers:
            w.cancel()

    wall_elapsed = time.monotonic() - wall_start
    total_done = len(create_stats.latencies) + len(edit_stats.latencies) + len(audit_stats.latencies)
    all_latencies = create_stats.latencies + edit_stats.latencies + audit_stats.latencies
    total_errors = create_stats.errors + edit_stats.errors + audit_stats.errors

    print(f"\n{'='*60}")
    print(f"RESULTS  ({total_done} requests in {wall_elapsed:.1f}s — {total_done/wall_elapsed:.1f} RPS actual)")
    print(f"{'='*60}")
    create_stats.report("POST /api/resources/ (create)")
    print()
    edit_stats.report("PUT  /api/resources/{id} (edit)")
    print()
    audit_stats.report("GET  /admin/audit-log (audit)")

    if all_latencies:
        s = sorted(all_latencies)
        n = len(s)
        print(f"\n  OVERALL ({n} reqs, {total_errors} errors):")
        print(f"    p50={s[n//2]:.0f}ms  p90={s[int(n*.9)]:.0f}ms  p99={s[int(n*.99)]:.0f}ms  max={s[-1]:.0f}ms")
        success = sum(c for st in (create_stats, edit_stats, audit_stats)
                      for k, c in st.status_counts.items() if k < 400)
        print(f"    success rate: {success/n*100:.1f}%")

    # Cleanup: delete all created resources (semaphore-throttled to avoid overwhelming the server)
    print(f"\nCleaning up {len(created_ids)} created resources...")
    sem = asyncio.Semaphore(10)
    deleted = 0

    async def _delete(client: httpx.AsyncClient, rid: int):
        nonlocal deleted
        async with sem:
            r = await client.delete(f"{BASE}/api/resources/{rid}", headers=HEADERS)
            if r.status_code == 204:
                deleted += 1

    async with httpx.AsyncClient(timeout=10.0) as client:
        await asyncio.gather(*[_delete(client, rid) for rid in created_ids], return_exceptions=True)
    print(f"Deleted {deleted}/{len(created_ids)} resources.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rps", type=int, default=50)
    parser.add_argument("--duration", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(run(args.rps, args.duration))
