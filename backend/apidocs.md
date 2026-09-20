# SafeWalk API Documentation

This document describes the current SafeWalk backend API for Android/frontend integration.

Base URL after deployment:

```
https://your-api-host.example.com/api/v1
```

Local development base URL:

```
http://localhost:8000/api/v1
```

Android emulator should usually use:

```
http://10.0.2.2:8000/api/v1
```

## General notes

- All requests and responses are JSON.
- Coordinates use WGS84 decimal degrees.
- Latitude range: `-90` to `90`.
- Longitude range: `-180` to `180`.
- A safety score is from `0` to `1`, where `1` means safest.
- Factor score values are also from `0` to `1`, where `1` means safest.
- Production deployments should use HTTPS.
- Upstream failures are returned as safe generic errors; raw external API errors are not sent to the client.

## Default headers

Use this for JSON requests:

```http
Content-Type: application/json
```

Optional JWT header for reports:

```http
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Authentication is required for `/auth/*`, `/trusted-contacts/*`, and `/safe-walk/*` endpoints.
Include the JWT in the `Authorization: Bearer <token>` header.

## Health check

### `GET /health`

Used to confirm the API and database are reachable.

Request:

```http
GET /api/v1/health
```

Example response:

```json
{
  "status": "ok",
  "environment": "development",
  "database_connected": true,
  "timestamp": "2026-09-07T12:00:00Z"
}
```

## Geocode an address

### `GET /geocode`

Converts an address into coordinates.

Request:

```http
GET /api/v1/geocode?address=1600%20Pennsylvania%20Avenue%20NW
```

Query parameters:

- `address` — required, string, between 2 and 300 characters.

Example response:

```json
{
  "coordinate": {
    "lat": 38.8977,
    "lon": -77.0365
  },
  "address": "1600 Pennsylvania Avenue NW, Washington, DC"
}
```

Use this when the user types a destination name.

## Reverse geocode coordinates

### `GET /reverse-geocode`

Converts coordinates into an address.

Request:

```http
GET /api/v1/reverse-geocode?lat=38.8977&lon=-77.0365
```

Query parameters:

- `lat` — required, number, `-90` to `90`.
- `lon` — required, number, `-180` to `180`.

Example response:

```json
{
  "address": "1600 Pennsylvania Avenue NW, Washington, DC"
}
```

Use this when the user drops a pin on the map or uses current location.

## Calculate a safe route

### `POST /route`

Returns a route between a start point and a destination.

Request body:

```json
{
  "start": {
    "lat": 38.8977,
    "lon": -77.0365
  },
  "destination": {
    "lat": 38.8895,
    "lon": -77.0353
  },
  "preference": "safest",
  "require_sidewalk": false
}
```

Fields:

- `start` — required object with `lat` and `lon`.
- `destination` — required object with `lat` and `lon`.
- `preference` — optional string.
  - `safest`
  - `fastest`
  - `balanced`
  - Defaults to `safest`.
- `require_sidewalk` — optional boolean.
  - `true` returns only routes where SafeWalk can confirm sidewalk availability throughout.
  - `false` does not enforce a sidewalk-only route.
  - Defaults to `false`.

This endpoint asks OSRM for up to `MAX_ROUTE_ALTERNATIVES` walking-route candidates, scores each with OpenStreetMap/lighting/sidewalk data, weather, crime, and active user reports, then returns the best route for the selected preference.

Example response:

```json
{
  "polyline": "encoded-polyline",
  "coordinates": [
    {"lat": 38.8977, "lon": -77.0365},
    {"lat": 38.8985, "lon": -77.0352}
  ],
  "distance_m": 1250.4,
  "estimated_walking_time_seconds": 900,
  "safety_score": 0.82,
  "factor_breakdown": {
    "crime": 0.9,
    "lighting": 0.8,
    "sidewalk": 1.0,
    "crosswalk": 0.7,
    "road_type": 0.8,
    "time_of_day": 1.0,
    "weather": 0.85,
    "user_reports": 0.75
  },
  "warnings": [
    "Parts of this route may have limited lighting."
  ]
}
```

Field meanings:

- `polyline` — encoded line that can be decoded into coordinates.
- `coordinates` — raw route coordinates, easiest to use directly with map SDKs.
- `distance_m` — route distance in meters.
- `estimated_walking_time_seconds` — estimated walking time in seconds.
- `safety_score` — overall route safety score from `0` to `1`.
- `factor_breakdown` — explainable per-factor safety scores.
- `warnings` — human-readable warnings the app can show to the user.

### Frontend route display

Android prefers using `coordinates`.

Example with Google Maps:

```kotlin
val points = response.coordinates.map {
    LatLng(it.lat, it.lon)
}

map.addPolyline(
    PolylineOptions()
        .addAll(points)
        .color(Color.BLUE)
        .width(12f)
)
```

The app can display `warnings` as cards or icons below the route.

The app can display `factor_breakdown` as progress bars or safety chips. `1` is safest.

## Submit a hazard report

### `POST /report`

Creates an anonymous report or, when a JWT is present, associates it with a user.

Request body:

```json
{
  "location": {
    "lat": 38.8977,
    "lon": -77.0365
  },
  "report_type": "poor_lighting",
  "description": "Several streetlights are out."
}
```

Fields:

- `location` — required object with `lat` and `lon`.
- `report_type` — required string.
  - `poor_lighting`
  - `construction`
  - `aggressive_animal`
  - `unsafe_activity`
  - `broken_sidewalk`
  - `other`
- `description` — optional string, max 2000 characters.

Example response:

```json
{
  "id": "b8e6aceb-a2a1-4ee2-9999-93c2cf872a18",
  "user_id": null,
  "location": {
    "lat": 38.8977,
    "lon": -77.0365
  },
  "report_type": "poor_lighting",
  "description": "Several streetlights are out.",
  "created_at": "2026-09-07T12:00:00Z",
  "status": "active"
}
```

## Authentication

### `POST /auth/register`

Register a new user account.

Request body:
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "display_name": "John Doe",
  "phone_number": "+15551234567"
}
```

Fields:
- `email` — required, valid email
- `password` — required, 8-128 characters
- `display_name` — optional, max 120 characters
- `phone_number` — optional, max 30 characters

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "John Doe",
    "phone_number": "+15551234567",
    "created_at": "2026-09-19T12:00:00Z"
  }
}
```

### `POST /auth/login`

Log in with email and password.

Request body:
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

Response: Same as register (returns new access token).

### `GET /auth/me`

Get current user profile. Requires `Authorization: Bearer <token>` header.

Response:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "phone_number": "+15551234567",
  "created_at": "2026-09-19T12:00:00Z"
}
```

## Trusted Contacts

### `POST /trusted-contacts`

Add a trusted contact. Requires authentication.

Request body:
```json
{
  "name": "Jane Smith",
  "phone_number": "+15559876543",
  "relation": "sister"
}
```

Fields:
- `name` — required, 1-120 characters
- `phone_number` — required, 7-30 characters
- `relation` — optional, max 80 characters

### `GET /trusted-contacts`

List all trusted contacts for the authenticated user.

Response:
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "name": "Jane Smith",
    "phone_number": "+15559876543",
    "relation": "sister",
    "is_active": true,
    "created_at": "2026-09-19T12:00:00Z"
  }
]
```

### `GET /trusted-contacts/{contact_id}`

Get a specific trusted contact.

### `DELETE /trusted-contacts/{contact_id}`

Delete a trusted contact.

## Safe Walk Sessions

### `POST /safe-walk/start`

Start a new safe walk session. Requires authentication.

Request body:
```json
{
  "start_location": {"lat": 38.8977, "lon": -77.0365},
  "destination": {"lat": 38.8895, "lon": -77.0353},
  "expected_arrival_at": "2026-09-19T13:30:00Z"
}
```

Fields:
- `start_location` — required, current location
- `destination` — required, destination coordinates
- `expected_arrival_at` — optional ISO 8601 datetime

Response:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "status": "active",
  "destination": {"lat": 38.8895, "lon": -77.0353},
  "last_location": {"lat": 38.8977, "lon": -77.0365},
  "started_at": "2026-09-19T12:00:00Z",
  "ended_at": null,
  "last_updated_at": "2026-09-19T12:00:00Z",
  "expected_arrival_at": "2026-09-19T13:30:00Z"
}
```

### `POST /safe-walk/{session_id}/update`

Update location during safe walk. Requires authentication.

Request body:
```json
{
  "location": {"lat": 38.8980, "lon": -77.0360}
}
```

### `POST /safe-walk/{session_id}/stop`

Stop the safe walk session. Requires authentication.

### `GET /safe-walk/active`

Get the currently active safe walk session (if any).

### `GET /safe-walk/{session_id}`

Get a specific safe walk session by ID.

## Nearby Hazard Reports

### `GET /reports/nearby`

Get active hazard reports near a location.

Query parameters:
- `lat` — required, `-90` to `90`
- `lon` — required, `-180` to `180`
- `radius_m` — optional, 100-10000, default 1000

Example:
```http
GET /api/v1/reports/nearby?lat=38.8977&lon=-77.0365&radius_m=500
```

Response:
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "location": {"lat": 38.8970, "lon": -77.0370},
    "report_type": "poor_lighting",
    "description": "Streetlight out",
    "created_at": "2026-09-19T12:00:00Z",
    "status": "active"
  }
]
```

## Updated Android API Contract

```kotlin
interface SafeWalkApi {
    @GET("api/v1/health")
    suspend fun health(): HealthResponse

    @GET("api/v1/geocode")
    suspend fun geocode(@Query("address") address: String): GeocodeResponse

    @GET("api/v1/reverse-geocode")
    suspend fun reverseGeocode(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double
    ): ReverseGeocodeResponse

    @POST("api/v1/route")
    suspend fun calculateRoute(@Body request: RouteRequest): RouteResponse

    @POST("api/v1/report")
    suspend fun submitReport(
        @Header("Authorization") authorization: String?,
        @Body request: UserReportCreate
    ): UserReportRead

    @GET("api/v1/reports/nearby")
    suspend fun getNearbyReports(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("radius_m") radiusM: Int = 1000
    ): List<UserReportRead>

    @POST("api/v1/auth/register")
    suspend fun register(@Body request: RegisterRequest): TokenResponse

    @POST("api/v1/auth/login")
    suspend fun login(@Body request: LoginRequest): TokenResponse

    @GET("api/v1/auth/me")
    suspend fun getProfile(@Header("Authorization") auth: String): UserRead

    @POST("api/v1/trusted-contacts")
    suspend fun addTrustedContact(
        @Header("Authorization") auth: String,
        @Body request: TrustedContactCreate
    ): TrustedContactRead

    @GET("api/v1/trusted-contacts")
    suspend fun listTrustedContacts(@Header("Authorization") auth: String): List<TrustedContactRead>

    @DELETE("api/v1/trusted-contacts/{contactId}")
    suspend fun deleteTrustedContact(
        @Header("Authorization") auth: String,
        @Path("contactId") contactId: String
    )

    @POST("api/v1/safe-walk/start")
    suspend fun startSafeWalk(
        @Header("Authorization") auth: String,
        @Body request: SafeWalkStartRequest
    ): SafeWalkRead

    @POST("api/v1/safe-walk/{sessionId}/update")
    suspend fun updateSafeWalk(
        @Header("Authorization") auth: String,
        @Path("sessionId") sessionId: String,
        @Body request: SafeWalkUpdateRequest
    ): SafeWalkRead

    @POST("api/v1/safe-walk/{sessionId}/stop")
    suspend fun stopSafeWalk(
        @Header("Authorization") auth: String,
        @Path("sessionId") sessionId: String
    ): SafeWalkRead

    @GET("api/v1/safe-walk/active")
    suspend fun getActiveSafeWalk(@Header("Authorization") auth: String): SafeWalkRead?
}
```


## Error responses

The API may return these statuses.

### `422 Validation Error`

Returned when request input is invalid.

```json
{
  "detail": [
    {
      "loc": ["body", "start", "lat"],
      "msg": "Input should be less than or equal to 90",
      "type": "value_error"
    }
  ]
}
```

### `404 Not Found`

Returned when no route or address can be found.

```json
{
  "detail": "No route was found between those points."
}
```

When `require_sidewalk` is `true` and no sidewalk-confirmed route exists:

```json
{
  "detail": "No sidewalk-only route was found between those points."
}
```

### `503 Service Unavailable`

Returned when an upstream service is unavailable.

```json
{
  "detail": "Routing is temporarily unavailable."
}
```

### `500 Internal Server Error`

Returned for unexpected internal errors. The response is intentionally generic and does not expose internals.

```json
{
  "detail": "Internal server error"
}
```

## Suggested Android API contract

This is a Retrofit-style sketch based on the current API.

```kotlin
interface SafeWalkApi {
    @GET("api/v1/health")
    suspend fun health(): HealthResponse

    @GET("api/v1/geocode")
    suspend fun geocode(@Query("address") address: String): GeocodeResponse

    @GET("api/v1/reverse-geocode")
    suspend fun reverseGeocode(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double
    ): ReverseGeocodeResponse

    @POST("api/v1/route")
    suspend fun calculateRoute(@Body request: RouteRequest): RouteResponse

    @POST("api/v1/report")
    suspend fun submitReport(
        @Header("Authorization") authorization: String?,
        @Body request: UserReportCreate
    ): UserReportRead
}
```
