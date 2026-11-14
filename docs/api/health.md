# GET /health

Liveness/readiness probe; pings Redis.

```bash
curl localhost:8000/health
```

| Status | Body                                      | When          |
|--------|-------------------------------------------|---------------|
| 200    | `{"status": "ok", "redis": "up"}`         | Redis reachable |
| 503    | `{"status": "degraded", "redis": "down"}` | Redis ping failed |

Used by the compose `api` healthcheck. Code: `backend/app/main.py`.
