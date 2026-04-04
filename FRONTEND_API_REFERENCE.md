# Bibleway Frontend API Reference

All endpoints are prefixed with `/api/v1`. All responses use the envelope: `{"message": "...", "data": {...}}`.

Auth: JWT Bearer token in `Authorization: Bearer <token>` header (unless noted otherwise).

---

## Razorpay Web Payments

### Shop Product Purchase Flow

**Step 1 -- Create Order**

```
POST /api/v1/shop/razorpay/create-order/
```

Request:
```json
{
  "product_id": "<uuid>"
}
```

Response:
```json
{
  "message": "Razorpay order created successfully.",
  "data": {
    "order_id": "order_xxxxx",
    "amount": 1000,
    "currency": "INR",
    "razorpay_key": "rzp_live_xxxxx",
    "product_id": "<uuid>",
    "product_title": "Neon Cathedral"
  }
}
```

> `amount` is in **paise** (1000 = Rs.10). All paid wallpapers are Rs.10.

**Step 2 -- Open Razorpay Checkout**

Use the returned `order_id`, `amount`, `currency`, and `razorpay_key` to open the Razorpay checkout widget.

**Step 3 -- Verify Payment**

```
POST /api/v1/shop/razorpay/verify/
```

Request:
```json
{
  "product_id": "<uuid>",
  "razorpay_order_id": "order_xxxxx",
  "razorpay_payment_id": "pay_xxxxx",
  "razorpay_signature": "hex_signature_string"
}
```

Response:
```json
{
  "message": "Payment verified and purchase recorded successfully.",
  "data": {
    "id": "<uuid>",
    "product": {
      "id": "<uuid>",
      "title": "Neon Cathedral",
      "cover_image": "https://...",
      "category": "wallpaper",
      "is_free": false
    },
    "platform": "web",
    "transaction_id": "pay_xxxxx",
    "is_validated": true,
    "created_at": "2026-04-04T18:00:00Z"
  }
}
```

---

### Boost Purchase Flow (Web)

**Step 1 -- Create Boost Order**

```
POST /api/v1/analytics/boosts/razorpay/create-order/
```

Request:
```json
{
  "post_id": "<uuid>",
  "tier": "boost_tier_1",
  "duration_days": 7
}
```

Response:
```json
{
  "message": "Razorpay boost order created successfully.",
  "data": {
    "order_id": "order_xxxxx",
    "amount": 9900,
    "currency": "INR",
    "razorpay_key": "rzp_live_xxxxx",
    "post_id": "<uuid>",
    "tier": "boost_tier_1",
    "duration_days": 7
  }
}
```

**Boost Tier Pricing:**

| Tier | Price (paise) | Price (INR) |
|------|--------------|-------------|
| `boost_tier_1` | 9900 | Rs.99 |
| `boost_tier_2` | 24900 | Rs.249 |
| `boost_tier_3` | 49900 | Rs.499 |

**Step 2 -- Open Razorpay Checkout** (same as shop flow)

**Step 3 -- Verify Boost Payment**

```
POST /api/v1/analytics/boosts/razorpay/verify/
```

Request:
```json
{
  "post_id": "<uuid>",
  "tier": "boost_tier_1",
  "duration_days": 7,
  "razorpay_order_id": "order_xxxxx",
  "razorpay_payment_id": "pay_xxxxx",
  "razorpay_signature": "hex_signature_string"
}
```

Response:
```json
{
  "message": "Payment verified and boost activated successfully.",
  "data": {
    "id": "<uuid>",
    "post": "<uuid>",
    "user": "<uuid>",
    "tier": "boost_tier_1",
    "platform": "web",
    "duration_days": 7,
    "is_active": true,
    "activated_at": "2026-04-04T18:00:00Z",
    "expires_at": "2026-04-11T18:00:00Z",
    "created_at": "2026-04-04T18:00:00Z"
  }
}
```

---

## Shop Endpoints (Existing)

### List Products
```
GET /api/v1/shop/products/
GET /api/v1/shop/products/?category=wallpaper
```

Response fields: `id`, `title`, `cover_image`, `category`, `is_free`, `price`, `price_tier`, `apple_product_id`, `google_product_id`, `created_at`

Supports `ETag` / `If-None-Match` for 304 caching.

### Search Products
```
GET /api/v1/shop/products/search/?q=neon
```

### Get Product Detail
```
GET /api/v1/shop/products/<uuid>/
```

Additional fields: `description`, `download_count`, `download_url`, `updated_at`

> `download_url` is only present if the user owns the product (or it's free).

### Verify IAP Purchase (iOS/Android)
```
POST /api/v1/shop/purchases/
```

Request:
```json
{
  "product_id": "<uuid>",
  "platform": "ios" | "android",
  "receipt_data": "base64_receipt_or_token",
  "transaction_id": "apple_or_google_txn_id"
}
```

### List Purchases
```
GET /api/v1/shop/purchases/list/
```

### Download Product File
```
GET /api/v1/shop/downloads/<uuid:product_id>/
```

Returns `{"download_url": "pre_signed_s3_url"}`. Rate limited: 30/hour.

---

## Bible Highlights

### Create Highlight

```
POST /api/v1/bible/highlights/
```

**API Bible highlight:**
```json
{
  "highlight_type": "api_bible",
  "verse_reference": "JHN.3.16",
  "color": "yellow"
}
```

**Segregated Bible highlight (text selection):**
```json
{
  "highlight_type": "segregated",
  "content_type": 15,
  "object_id": "<page_uuid>",
  "selection_start": 120,
  "selection_end": 250,
  "color": "blue"
}
```

Colors: `yellow`, `green`, `blue`, `pink`, `orange`

### List Highlights
```
GET /api/v1/bible/highlights/
GET /api/v1/bible/highlights/?highlight_type=api_bible
GET /api/v1/bible/highlights/?highlight_type=segregated
GET /api/v1/bible/highlights/?content_type=15&object_id=<page_uuid>
```

### Delete Highlight
```
DELETE /api/v1/bible/highlights/<uuid>/
```

---

## Bible Bookmarks

### Create Bookmark
```
POST /api/v1/bible/bookmarks/
```

**API Bible:**
```json
{
  "bookmark_type": "api_bible",
  "verse_reference": "GEN.1.1"
}
```

**Segregated:**
```json
{
  "bookmark_type": "segregated",
  "content_type": 15,
  "object_id": "<page_uuid>"
}
```

### List Bookmarks
```
GET /api/v1/bible/bookmarks/
```

### Delete Bookmark
```
DELETE /api/v1/bible/bookmarks/<uuid>/
```

---

## Bible Notes

### Create Note
```
POST /api/v1/bible/notes/
```

```json
{
  "note_type": "api_bible",
  "verse_reference": "PSA.23.1",
  "text": "My reflection on this verse..."
}
```

### Update Note
```
PATCH /api/v1/bible/notes/<uuid>/
```

```json
{
  "text": "Updated note text"
}
```

### List Notes
```
GET /api/v1/bible/notes/
```

### Delete Note
```
DELETE /api/v1/bible/notes/<uuid>/
```

---

## Bible Content

### List Sections
```
GET /api/v1/bible/sections/
```

### List Chapters
```
GET /api/v1/bible/sections/<uuid>/chapters/
```

### List Pages
```
GET /api/v1/bible/chapters/<uuid>/pages/
```

### Get Page Detail
```
GET /api/v1/bible/pages/<uuid>/
GET /api/v1/bible/pages/<uuid>/?language=hi
```

### Search Content
```
GET /api/v1/bible/search/?q=love
```

### API Bible Proxy
```
GET /api/v1/bible/api-bible/bibles
GET /api/v1/bible/api-bible/bibles/<bible_id>/books
GET /api/v1/bible/api-bible/bibles/<bible_id>/chapters/<chapter_id>?content-type=html
```

---

## Analytics Endpoints

### Record View/Share
```
POST /api/v1/analytics/views/
```

```json
{
  "content_type_model": "post" | "prayer",
  "object_id": "<uuid>",
  "view_type": "view" | "share"
}
```

### Post Analytics (author only)
```
GET /api/v1/analytics/posts/<uuid:post_id>/
```

Response: `{"views": 100, "reactions": 25, "comments": 10, "shares": 5}`

### User Analytics
```
GET /api/v1/analytics/me/
```

Response: `{"post_count": 15, "total_views": 500, "total_reactions": 150, "total_comments": 75}`

### Activate Boost (IAP)
```
POST /api/v1/analytics/boosts/
```

```json
{
  "post_id": "<uuid>",
  "tier": "boost_tier_1",
  "platform": "ios" | "android",
  "receipt_data": "receipt_string",
  "transaction_id": "txn_id",
  "duration_days": 7
}
```

### List Boosts
```
GET /api/v1/analytics/boosts/list/
GET /api/v1/analytics/boosts/list/?active_only=true
```

### Boost Analytics
```
GET /api/v1/analytics/boosts/<uuid>/analytics/
```

Response fields: `impressions`, `reach`, `engagement_rate`, `link_clicks`, `profile_visits`, `snapshot_date`

---

## Razorpay Webhook (Server-to-Server)

```
POST /api/v1/shop/razorpay/webhook/
```

- No auth required
- Razorpay signs the body with `X-Razorpay-Signature` header
- Listens for `payment.captured` events
- Auto-creates Purchase if frontend verify was missed
- Configure in Razorpay Dashboard > Settings > Webhooks

---

## Enums Reference

| Field | Values |
|-------|--------|
| Platform | `ios`, `android`, `web` |
| Highlight color | `yellow`, `green`, `blue`, `pink`, `orange` |
| Highlight/Bookmark/Note type | `api_bible`, `segregated` |
| View type | `view`, `share` |
| Boost tier | `boost_tier_1` (Rs.99), `boost_tier_2` (Rs.249), `boost_tier_3` (Rs.499) |

## Pagination

All list endpoints return:
```json
{
  "count": 100,
  "next": "...?page=2",
  "previous": null,
  "results": [...]
}
```

Page size: 20 items per page.

## Error Format

```json
{
  "message": "Error description",
  "data": { "field": ["error detail"] }
}
```

Common status codes: `400` (validation), `401` (unauthorized), `403` (forbidden), `404` (not found), `409` (duplicate transaction), `429` (rate limited).
