# Load Balancer

Simple Python load balancer that proxies HTTP requests across a pool of backend servers, keeps health state up to date, and provides a tunable load-testing harness.

## Features

- Round-robin routing with automatic removal of unhealthy backends.
- Background health checker that polls `GET /health` periodically.
- Thread pool worker model so multiple client sockets are handled concurrently.
- Structured logging (request routing, backend latency, health flips).
- Companion `threadtest.py` script for reproducible load and latency measurements.

## Prerequisites

- Python 3.9+
- `requests` library (`pip install requests`)

## Running the Demo Backends

From the `backend-servers` directory, start three static servers:

```bash
python -m http.server 8080 --directory server8080 &
python -m http.server 8081 --directory server8081 &
python -m http.server 8082 --directory server8082 &
```

## Starting the Load Balancer

From the repo root:

```bash
python lbMultiThreading.py [health_check_period_seconds]
```

- Listens on `127.0.0.1:9090`.
- Optional CLI argument sets the health check interval (default 10 seconds, floored at 1).
- Logs show which backend served each client and how long the backend response took.

## Health Checking

- `updateHealthyServers()` runs in a daemon thread and polls each backend using `GET /health`.
- Healthy servers are tracked in a shared set guarded by locks.
- When the set becomes empty, clients receive `503 Service Unavailable` responses.
- Logging levels:
  - `INFO` for servers flipping healthy/unhealthy and routing summaries.
  - `DEBUG` (enable via `LOGLEVEL=DEBUG` or editing `basicConfig`) for payload traces.

## Load Testing Script

Use `threadtest.py` to simulate concurrent clients. Example:

```bash
python threadtest.py \
	--url http://127.0.0.1:9090/ \
	--total 800 \
	--concurrency 25 50 100 150 200 250 \
	--rounds 2 \
	--timeout 4
```

What it provides:

- Runs each concurrency level for the requested number of rounds.
- Records total time, success/error counts, throughput, and latency percentiles (avg/p50/p95/max).
- Prints a summary table so you can compare how performance changes with load.

## Observability Tips

Tail balancer logs while running `threadtest.py` to correlate routing decisions with latency. Point `basicConfig` at a file (or lower the log level) if you need persistent traces. The first concurrency level that produces errors approximates current capacity.
