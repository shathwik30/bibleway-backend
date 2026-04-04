# API Bible Preview Mode

Unauthenticated users can now access the `/api/v1/bible/api-bible/` proxy endpoint without a JWT token. Instead of a `401 Unauthorized` error, they receive a **preview** of the content.

## How it works

| Scenario | Behavior |
|---|---|
| **Authenticated** | Full response data, as before |
| **Unauthenticated** | Truncated preview + `message: "Preview — sign in to view full content."` |

### Preview limits

- **List endpoints** (e.g. `/bibles/`, `/bibles/<id>/books/`): first **3 items** only
- **Content endpoints** (e.g. chapter HTML): first **500 characters**, truncated with `…`
- **Search results** (`verses` array): first **3 verses** only

### Response example (unauthenticated)

```json
{
  "message": "Preview — sign in to view full content.",
  "data": { "content": "<p>In the beginning God created…", "id": "GEN.1" }
}
```

## Configuration

Limits are set as class attributes on `ApiBibleProxyView` in `apps/bible/views.py`:

- `PREVIEW_LIST_LIMIT = 3`
- `PREVIEW_CONTENT_MAX_CHARS = 500`
