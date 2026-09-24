# Load Test Results

Measured 2026-09-24 against the live private Cloud Run revision through an
authenticated `gcloud run services proxy` on `127.0.0.1:9090`.

## Environment

| Field | Value |
|---|---|
| Service / region | `fraud-risk-api` / `europe-west1` |
| Revision | `fraud-risk-api-00009-hiz` |
| Model release / version | `v2-3e65f5fd-88b81f0` / `2` |
| Instance configuration | 1 CPU, 1 GiB, container concurrency 4, min 0, max 3 |
| Client | macOS arm64, US/Pacific, private Cloud Run proxy |
| Workload | Known negative `/predict` sample; 100 requests per concurrency level |
| State | Warm revision; every response validated for status, probability, class, and threshold |

## Results

| Concurrency | Requests | RPS | p50 ms | p95 ms | p99 ms | Error rate |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 100 | 14.452 | 68.747 | 72.816 | 74.927 | 0.0% |
| 10 | 100 | 104.809 | 93.296 | 113.115 | 119.522 | 0.0% |
| 25 | 100 | 204.592 | 109.290 | 163.153 | 178.854 | 0.0% |
| 50 | 100 | 176.330 | 210.666 | 322.036 | 328.409 | 0.0% |

The short run peaks near concurrency 25. At concurrency 50, throughput falls
about 13.8% while p95 latency nearly doubles, indicating queueing/contention
past the useful concurrency range for this small configuration. These are
point-in-time measurements through a local authenticated proxy, not an SLO or
capacity guarantee. Longer tests from a region close to `europe-west1` are
needed before using the figures for capacity planning.

An exploratory run that overlapped proxy/cold-start recovery was excluded from
the comparison because it did not hold warm-state conditions constant. Its
failure was retained as an operational observation rather than mixed into the
reported warm matrix.

## Reproduction

Start a fresh authenticated proxy:

```bash
gcloud run services proxy fraud-risk-api \
  --project=fraud-risk-engine \
  --region=europe-west1 \
  --port=9090
```

Then run each level with the tracked client:

```bash
python -m scripts.load_test \
  --service-url=http://127.0.0.1:9090 \
  --concurrency=25 \
  --requests=100 \
  --environment="production via gcloud private proxy; warm revision" \
  --revision=fraud-risk-api-00009-hiz \
  --model-release=v2-3e65f5fd-88b81f0 \
  --instance-config="Cloud Run europe-west1; 1 CPU; 1Gi; concurrency 4; min 0; max 3"
```
