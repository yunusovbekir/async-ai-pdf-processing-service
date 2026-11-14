# GET /batches/{id}/events

Stream document status changes of a batch as [Server-Sent Events](https://developer.mozilla.org/docs/Web/API/Server-sent_events). Use it instead of polling [GET /batches/{id}](get-batch.md).

```bash
curl -N localhost:8000/batches/9f1c.../events
```

Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

**Events**

| Event | Data | When |
| --- | --- | --- |
| `snapshot` | Full batch, same body as `GET /batches/{id}` | Once, at start |
| `document` | Fresh document (no pages): status, summary_status, summary, error, page_count, ... | On every status change |
| `done` | `{}` | Every document is `completed` or `failed`; the stream then closes (also sent right after `snapshot` for finished batches) |
| `: ping` | SSE comment | Every `SSE_HEARTBEAT_SECONDS` (default 15) without other traffic |

```
event: snapshot
data: {"id":"9f1c...","parser":"pypdf","created_at":"...","documents":[...]}

event: document
data: {"id":"3a7e...","batch_id":"9f1c...","status":"completed","summary_status":"completed","summary":"...",...}

event: done
data: {}
```

The server subscribes before reading the snapshot, so no change is lost. The stream closes after `SSE_MAX_DURATION_SECONDS` (default 600) or on client disconnect; reconnect to resume, since the snapshot always reflects the current state (`Last-Event-ID` is not needed).

**Errors:** `404` (JSON) if the batch is unknown or expired.
