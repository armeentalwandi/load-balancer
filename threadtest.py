#!/usr/bin/env python3
"""Threaded HTTP load tester for the local balancer."""

import argparse
import statistics
import threading
import time

import requests


def run_once(url, total, concurrency, timeout):
    results = [None] * total
    idx_lock = threading.Lock()
    next_idx = 0

    def worker():
        nonlocal next_idx
        while True:
            with idx_lock:
                if next_idx >= total:
                    return
                req_idx = next_idx
                next_idx += 1
            start = time.time()
            try:
                resp = requests.get(url, timeout=timeout)
                results[req_idx] = ("OK", resp.status_code, time.time() - start)
            except Exception as exc:
                results[req_idx] = ("ERR", str(exc), None)

    threads = []
    t0 = time.time()
    for _ in range(concurrency):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    elapsed = time.time() - t0

    oks = [entry for entry in results if entry and entry[0] == "OK"]
    errs = [entry for entry in results if entry and entry[0] == "ERR"]
    latencies = [entry[2] for entry in oks]

    return {
        "url": url,
        "total": total,
        "concurrency": concurrency,
        "elapsed": elapsed,
        "oks": len(oks),
        "errs": len(errs),
        "latencies": latencies,
        "errors": errs[:5],
    }


def percentile(sorted_values, pct):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = int(round((pct / 100) * (len(sorted_values) - 1)))
    return sorted_values[idx]


def print_report(stats, run_label=None):
    latencies = stats["latencies"]
    latency_line = "Latency ms: n/a"
    if latencies:
        lat_sorted = sorted(latencies)
        latency_line = (
            "Latency ms: avg={avg:.1f} p50={p50:.1f} p95={p95:.1f} max={mx:.1f}"
        ).format(
            avg=statistics.mean(lat_sorted) * 1000,
            p50=percentile(lat_sorted, 50) * 1000,
            p95=percentile(lat_sorted, 95) * 1000,
            mx=lat_sorted[-1] * 1000,
        )

    print("=" * 60)
    if run_label:
        print(run_label)
    print(f"URL: {stats['url']}")
    print(f"Total requests: {stats['total']}")
    print(f"Concurrency: {stats['concurrency']}")
    print(f"Elapsed: {stats['elapsed']:.2f}s")
    print(f"Successful: {stats['oks']}  Errors: {stats['errs']}")
    print(latency_line)
    if stats["errors"]:
        print("Sample errors:")
        for err in stats["errors"]:
            print("  ", err)


def parse_args():
    parser = argparse.ArgumentParser(description="Stress the local load balancer")
    parser.add_argument("--url", default="http://127.0.0.1:9090/", help="Target URL served via the balancer")
    parser.add_argument("--total", type=int, default=200, help="Total requests per run")
    parser.add_argument(
        "--concurrency",
        type=int,
        nargs="+",
        default=[50],
        help="One or more worker counts to sweep",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-request timeout in seconds")
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Repeat each concurrency level this many times",
    )
    return parser.parse_args()


def print_summary(all_stats):
    if not all_stats:
        return
    print("\n" + "#" * 60)
    print("Test summary")
    print("#" * 60)
    header = f"{'Run':<10}{'Conc':<8}{'Total':<8}{'OK':<8}{'Err':<8}{'Req/s':<10}{'Avg ms':<10}"
    print(header)
    for idx, stats in enumerate(all_stats, start=1):
        throughput = (stats["oks"] / stats["elapsed"]) if stats["elapsed"] else 0.0
        avg_ms = (
            statistics.mean(stats["latencies"]) * 1000
            if stats["latencies"]
            else 0.0
        )
        label = stats.get("label", f"run-{idx}")
        row = f"{label:<10}{stats['concurrency']:<8}{stats['total']:<8}{stats['oks']:<8}{stats['errs']:<8}{throughput:<10.1f}{avg_ms:<10.1f}"
        print(row)


def main():
    args = parse_args()
    all_stats = []
    for level in args.concurrency:
        for round_idx in range(1, args.rounds + 1):
            stats = run_once(args.url, args.total, level, args.timeout)
            stats["label"] = f"c{level}-r{round_idx}"
            print_report(stats, run_label=f"Run {round_idx}/{args.rounds} @ concurrency={level}")
            all_stats.append(stats)
    print_summary(all_stats)


if __name__ == "__main__":
    main()

# python threadtest.py --url http://127.0.0.1:9090/ --total 400 --concurrency 25 50 100 --rounds 3 --timeout 4
# ============================================================
# Run 1/3 @ concurrency=25
# URL: http://127.0.0.1:9090/
# Total requests: 400
# Concurrency: 25
# Elapsed: 0.52s
# Successful: 400  Errors: 0
# Latency ms: avg=32.2 p50=29.1 p95=62.1 max=102.7
# ============================================================
# Run 2/3 @ concurrency=25
# URL: http://127.0.0.1:9090/
# Total requests: 400
# Concurrency: 25
# Elapsed: 0.49s
# Successful: 400  Errors: 0
# Latency ms: avg=28.9 p50=26.8 p95=53.5 max=75.9
# ============================================================
# Run 3/3 @ concurrency=25
# URL: http://127.0.0.1:9090/
# Total requests: 400
# Concurrency: 25
# Elapsed: 0.45s
# Successful: 400  Errors: 0
# Latency ms: avg=26.2 p50=24.7 p95=41.0 max=63.0
# ============================================================
# Run 1/3 @ concurrency=50
# URL: http://127.0.0.1:9090/
# Total requests: 400
# Concurrency: 50
# Elapsed: 0.46s
# Successful: 400  Errors: 0
# Latency ms: avg=43.4 p50=39.8 p95=75.9 max=111.3
# ============================================================
# Run 2/3 @ concurrency=50
# URL: http://127.0.0.1:9090/
# Total requests: 400
# Concurrency: 50
# Elapsed: 0.48s
# Successful: 400  Errors: 0
# Latency ms: avg=45.3 p50=42.6 p95=79.2 max=131.8
# ============================================================
# Run 3/3 @ concurrency=50
# URL: http://127.0.0.1:9090/
# Total requests: 400
# Concurrency: 50
# Elapsed: 0.46s
# Successful: 400  Errors: 0
# Latency ms: avg=42.9 p50=39.8 p95=80.0 max=111.6
# ============================================================
# Run 1/3 @ concurrency=100
# URL: http://127.0.0.1:9090/
# Total requests: 400
# Concurrency: 100
# Elapsed: 0.47s
# Successful: 400  Errors: 0
# Latency ms: avg=44.4 p50=42.5 p95=80.8 max=122.9
# ============================================================
# Run 2/3 @ concurrency=100
# URL: http://127.0.0.1:9090/
# Total requests: 400
# Concurrency: 100
# Elapsed: 0.48s
# Successful: 400  Errors: 0
# Latency ms: avg=45.2 p50=42.9 p95=87.2 max=127.6
# ============================================================
# Run 3/3 @ concurrency=100
# URL: http://127.0.0.1:9090/
# Total requests: 400
# Concurrency: 100
# Elapsed: 0.45s
# Successful: 400  Errors: 0
# Latency ms: avg=45.2 p50=44.0 p95=78.2 max=111.0

# ############################################################
# Test summary
# ############################################################
# Run       Conc    Total   OK      Err     Req/s     Avg ms    
# c25-r1    25      400     400     0       763.8     32.2      
# c25-r2    25      400     400     0       810.6     28.9      
# c25-r3    25      400     400     0       883.9     26.2      
# c50-r1    50      400     400     0       863.1     43.4      
# c50-r2    50      400     400     0       828.7     45.3      
# c50-r3    50      400     400     0       869.0     42.9      
# c100-r1   100     400     400     0       848.3     44.4      
# c100-r2   100     400     400     0       827.6     45.2      
# c100-r3   100     400     400     0       888.9     45.2      