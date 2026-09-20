# Local Testing Setup

Run the full stack locally with real external services (OSRM, Nominatim, etc.)

## Quick Start

```bash
cd /Users/keshav/Documents/Other\ Coding/CAC/backend

# 1. Start database + API
docker compose -f docker-compose.local.yml up --build -d

# 2. Wait for services to be ready (~10-15 seconds)
# Check logs:
docker compose -f docker-compose.local.yml logs -f

# 3. Run migrations
docker compose -f docker-compose.local.yml exec api alembic upgrade head

# 4. Run integration tests
python test_local.py
```

## What This Tests

| Category | Endpoints | External Services |
|----------|-----------|-------------------|
| **System** | `/health` | Postgres + PostGIS |
| **Geocoding** | `/geocode`, `/reverse-geocode` | Nominatim (OSM) |
| **Routing** | `/route` | OSRM (project-osrm.org + fallback) |
| **Auth** | `/auth/register`, `/login`, `/me` | Database |
| **Trusted Contacts** | `/trusted-contacts/*` | Database + JWT |
| **Safe Walk** | `/safe-walk/*` | Database + JWT |
| **Reports** | `/reports`, `/reports/nearby` | Database |

## Expected Results

All tests should pass (✅). Typical output:

```
=== SafeWalk Local Integration Test ===

--- System ---
✅ GET /health → 200 (expected 200)
   DB Connected: True
   Env: development

--- Geocoding ---
✅ GET /geocode → 200 (expected 200)
   → 40.7580, -73.9855
✅ GET /reverse-geocode → 200 (expected 200)

--- Routing ---
✅ POST /route → 200 (expected 200)
   Safety: 0.82
   Distance: 1250m
   Warnings: ["Parts of this route may have limited lighting."]

--- Auth ---
✅ POST /auth/register → 201 (expected 201)
   Token: eyJhbGciOiJIUzI1NiIs...
✅ POST /auth/login → 200 (expected 200)
✅ GET /auth/me → 200 (expected 200)

--- Trusted Contacts ---
✅ POST /trusted-contacts → 201 (expected 201)
✅ GET /trusted-contacts → 200 (expected 200)
✅ DELETE /trusted-contacts/... → 204 (expected 204)

--- Safe Walk ---
✅ POST /safe-walk/start → 201 (expected 201)
✅ POST /safe-walk/.../update → 200 (expected 200)
✅ GET /safe-walk/active → 200 (expected 200)
✅ POST /safe-walk/.../stop → 200 (expected 200)

--- Reports ---
✅ POST /reports → 201 (expected 201)
✅ POST /reports/report → 201 (expected 201)
✅ GET /reports/nearby → 200 (expected 200)
   Found 2 nearby reports

============================================================
Total: 18/18 passed
🎉 All tests passed! Ready for deployment.
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `database_connected: false` | Check `docker compose logs db` - wait for PostGIS to initialize |
| Routing 404/500 | OSRM rate limited - try again, or check `docker compose logs api` |
| Geocoding 503 | Nominatim rate limit (1 req/sec) - wait a moment |
| Auth 500 | Check bcrypt version - ensure password ≤ 72 chars |
| Port 5432/8000 in use | Stop other services: `docker compose down` |

## Stop & Cleanup

```bash
# Stop services
docker compose -f docker-compose.local.yml down

# Remove volumes (fresh DB next time)
docker compose -f docker-compose.local.yml down -v
```

## Environment Variables

Edit `.env.local` to change:
- `JWT_SECRET_KEY` - for token signing
- `NOMINATIM_USER_AGENT` - required by Nominatim
- `MAX_ROUTE_ALTERNATIVES` - OSRM alternatives (default 3)
- `OSRM_BASE_URL` - override for custom OSRM instance

## For Production Deploy

After local tests pass:
```bash
git add .
git commit -m "Local integration tests passing"
git push origin main
# Render auto-deploys
```
