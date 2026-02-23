## Load Balancer Playground

This repo contains two lightweight HTTP load balancers plus a threaded stress tester:

- [lbMultiThreading.py](lbMultiThreading.py) — thread-pooled load balancer built on sockets.
- [lbasync.py](lbasync.py) — asyncio-based load balancer with the same round-robin and health-checking logic.
- [singularbackend.py](singularbackend.py) — barebones HTTP backend for local testing (status 200 reply).
- [threadtest.py](threadtest.py) — threaded client used to stress the balancer and report latency/throughput.

All balancers listen on `127.0.0.1:9090` and forward to three local backends on ports `8080`, `8081`, and `8082`.

### Requirements

- Python 3.10+ (tested on macOS)
- `requests` library for `threadtest.py` (install with `pip install requests`)

### Backend Servers

There are static HTML test backends under `backend-servers/server8080`, `server8081`, and `server8082`, each exposing a `/health` file. You can spin them up with Python’s built-in server:

```bash
cd backend-servers
python -m http.server 8080 --directory server8080
python -m http.server 8081 --directory server8081
python -m http.server 8082 --directory server8082
```

Or run the simple Python backend instead:

```bash
python singularbackend.py
```

### Threaded Load Balancer

[lbMultiThreading.py](lbMultiThreading.py) uses a `ThreadPoolExecutor` (default 50 workers) to proxy requests to healthy backends in round-robin order.

- Health checks: HTTP GET `/health` every `health_check_period` seconds (default 10). Mark servers healthy/unhealthy dynamically.
- Failure behavior: if no backend is healthy, responds `503`; other exceptions surface as `502`.

Run it:

```bash
python lbMultiThreading.py            # uses 10s health checks
python lbMultiThreading.py 5          # custom 5s health checks
```

### Asyncio Load Balancer

[lbasync.py](lbasync.py) mirrors the same logic using asyncio and `aiohttp` for health checks.

- Concurrency: `asyncio.start_server` spawns a coroutine per client; backpressure via `drain()`.
- Health checks: background task polling `/health` every `health_check_period` seconds (default 10, override via first CLI arg).
- Failure behavior: `503` when all backends are unhealthy, otherwise proxies responses; unexpected errors return `502`.

Run it:

```bash
python lbasync.py            # default 10s health checks
python lbasync.py 3          # custom 3s health checks
```

### Health Checking

- Path: `/health` on each backend.
- Marking: servers transition between healthy/unhealthy sets; selection happens only from the current healthy set.
- Threaded version uses raw sockets; asyncio version uses `aiohttp` with 5s timeout.

### Stress Testing

The threaded tester sweeps concurrency levels, collects latency percentiles, and reports request rate.

Common commands used during local runs:

```bash
# Example sweep: 800 requests, multiple concurrencies, two rounds
python threadtest.py --url http://127.0.0.1:9090/ --total 800 --concurrency 25 50 100 150 200 --rounds 2 --timeout 5

# Another sweep (smaller set)
python threadtest.py --url http://127.0.0.1:9090/ --total 800 --concurrency 25 50 75 100 --rounds 2 --timeout 5
```

Sample results from recent runs (all requests succeeded, backends were the Python HTTP servers):

- `concurrency=25`, `total=400` (3 rounds): avg latency 26–32 ms, throughput ~760–880 req/s, 0 errors.
- `concurrency=50`, `total=400` (3 rounds): avg latency 42–45 ms, throughput ~830–870 req/s, 0 errors.
- `concurrency=100`, `total=400` (3 rounds): avg latency ~44–45 ms, throughput ~830–890 req/s, 0 errors.

### Observations

- The plain `python -m http.server` backends are single-threaded; under very bursty load they may drop connections, which appear as `RemoteDisconnected` in the tester. Using more capable backends (threaded/async) or dialing down concurrency avoids this.
- Both balancers honor the healthy set before routing; if all backends fail health checks, clients see `503` until a backend recovers.

### Future Enhancements

- Add weighted round robin and least-connections strategies alongside the current simple round robin.
- Implement active retries with per-backend circuit breaking to avoid flapping and reduce tail latency.
- Support graceful shutdown and connection draining for both balancers to prevent mid-flight request drops.


### Suggested Workflow

1. Start three backends (or the simple Python backend) exposing `/health`.
2. Start either the threaded or asyncio balancer on port 9090.
3. Run `threadtest.py` sweeps to validate throughput and latency; adjust `health_check_period` and backend count as needed.
4. Inspect logs for health transitions and routing decisions.
