#!/usr/bin/env python3
"""
Manual API test script for SafeWalk backend.
Run against deployed API to verify all endpoints work correctly.

Usage:
    python test_api_manual.py --base-url https://safewalk-backend-l7a7.onrender.com/api/v1
    python test_api_manual.py --base-url http://localhost:8000/api/v1
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from typing import Any

import httpx


class SafeWalkAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)
        self.auth_token: str | None = None
        self.user_id: str | None = None
        self.contact_id: str | None = None
        self.session_id: str | None = None

    async def close(self):
        await self.client.aclose()

    def auth_header(self) -> dict[str, str]:
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        return {}

    async def request(
        self, method: str, path: str, **kwargs
    ) -> tuple[int, dict[str, Any] | list[Any] | str]:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers.update(self.auth_header())
        try:
            resp = await self.client.request(method, url, headers=headers, **kwargs)
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return resp.status_code, data
        except httpx.RequestError as e:
            return 0, f"Request failed: {e}"

    def print_result(self, name: str, status: int, data: Any, expected: int = 200):
        ok = "✅" if status == expected else "❌"
        print(f"\n{ok} {name} — HTTP {status} (expected {expected})")
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2, default=str)[:2000])
        else:
            print(data)

    # ==================== SYSTEM ENDPOINTS ====================

    async def test_health(self):
        status, data = await self.request("GET", "/health")
        self.print_result("GET /health", status, data, 200)
        assert status == 200
        assert data.get("status") == "ok"
        assert data.get("database_connected") is True

    async def test_geocode(self):
        # Test multiple addresses
        addresses = [
            "Times Square, New York, NY",
            "1600 Pennsylvania Ave NW, Washington, DC",
            "Golden Gate Bridge, San Francisco, CA",
            "Space Needle, Seattle, WA",
        ]
        for addr in addresses:
            status, data = await self.request("GET", "/geocode", params={"address": addr})
            self.print_result(f"GET /geocode ({addr[:30]}...)", status, data, 200)
            if status == 200:
                assert "coordinate" in data
                assert "lat" in data["coordinate"]
                assert "lon" in data["coordinate"]
                print(f"   → {data['coordinate']}")

    async def test_reverse_geocode(self):
        # Test multiple coordinates
        coords = [
            (40.7580, -73.9855),  # Times Square
            (38.8977, -77.0365),  # White House
            (37.8199, -122.4783), # Golden Gate Bridge
            (47.6205, -122.3493), # Space Needle
        ]
        for lat, lon in coords:
            status, data = await self.request("GET", "/reverse-geocode", params={"lat": lat, "lon": lon})
            self.print_result(f"GET /reverse-geocode ({lat},{lon})", status, data, 200)
            if status == 200:
                assert "address" in data
                print(f"   → {data['address'][:80]}...")

    # ==================== ROUTING ENDPOINTS ====================

    async def test_route_basic(self):
        """Test basic route with different preferences"""
        routes = [
            {
                "name": "NYC: Times Square → Central Park (safest)",
                "start": {"lat": 40.7580, "lon": -73.9855},
                "dest": {"lat": 40.7829, "lon": -73.9654},
                "preference": "safest",
            },
            {
                "name": "DC: White House → Capitol (fastest)",
                "start": {"lat": 38.8977, "lon": -77.0365},
                "dest": {"lat": 38.8895, "lon": -77.0090},
                "preference": "fastest",
            },
            {
                "name": "SF: Ferry Building → Fisherman's Wharf (balanced)",
                "start": {"lat": 37.7955, "lon": -122.3937},
                "dest": {"lat": 37.8080, "lon": -122.4177},
                "preference": "balanced",
            },
        ]

        for r in routes:
            payload = {
                "start": r["start"],
                "destination": r["dest"],
                "preference": r["preference"],
                "require_sidewalk": False,
                "return_alternatives": False,
            }
            status, data = await self.request("POST", "/route", json=payload)
            self.print_result(f"POST /route — {r['name']}", status, data, 200)
            if status == 200:
                assert "safety_score" in data
                assert "coordinates" in data
                assert "polyline" in data
                assert "warnings" in data
                assert "factor_breakdown" in data
                print(f"   → Safety: {data['safety_score']:.2f}, Distance: {data['distance_m']:.0f}m, Time: {data['estimated_walking_time_seconds']:.0f}s")
                print(f"   → Warnings: {data['warnings']}")

    async def test_route_with_alternatives(self):
        """Test route with alternatives returned"""
        payload = {
            "start": {"lat": 40.7580, "lon": -73.9855},
            "destination": {"lat": 40.7829, "lon": -73.9654},
            "preference": "safest",
            "require_sidewalk": False,
            "return_alternatives": True,
        }
        status, data = await self.request("POST", "/route", json=payload)
        self.print_result("POST /route (with alternatives)", status, data, 200)
        if status == 200:
            assert "routes" in data
            assert "selected_index" in data
            print(f"   → {len(data['routes'])} alternatives, selected index: {data['selected_index']}")

    async def test_route_require_sidewalk(self):
        """Test sidewalk enforcement"""
        payload = {
            "start": {"lat": 40.7580, "lon": -73.9855},
            "destination": {"lat": 40.7829, "lon": -73.9654},
            "preference": "safest",
            "require_sidewalk": True,
        }
        status, data = await self.request("POST", "/route", json=payload)
        self.print_result("POST /route (require_sidewalk=true)", status, data, 200)
        # May return 404 if no sidewalk-only route exists - that's valid

    async def test_route_validation_errors(self):
        """Test input validation"""
        # Invalid lat
        payload = {"start": {"lat": 95, "lon": -73.9855}, "destination": {"lat": 40.78, "lon": -73.96}}
        status, data = await self.request("POST", "/route", json=payload)
        self.print_result("POST /route (invalid lat)", status, data, 422)

        # Missing fields
        payload = {"start": {"lat": 40.75}}
        status, data = await self.request("POST", "/route", json=payload)
        self.print_result("POST /route (missing fields)", status, data, 422)

    # ==================== AUTH ENDPOINTS ====================

    async def test_auth_register(self):
        email = f"test_{datetime.now(UTC).timestamp()}@example.com"
        payload = {
            "email": email,
            "password": "TestPass123!",
            "display_name": "Test User",
            "phone_number": "+15551234567",
        }
        status, data = await self.request("POST", "/auth/register", json=payload)
        self.print_result("POST /auth/register", status, data, 201)
        if status == 201:
            assert "access_token" in data
            assert "user" in data
            self.auth_token = data["access_token"]
            self.user_id = data["user"]["id"]
            print(f"   → Got token, user_id: {self.user_id}")

    async def test_auth_login(self):
        # Register first if needed
        if not self.auth_token:
            await self.test_auth_register()

        # Login with same credentials
        email = f"test_{datetime.now(UTC).timestamp()}@example.com"
        payload = {"email": email, "password": "TestPass123!"}
        status, data = await self.request("POST", "/auth/login", json=payload)
        self.print_result("POST /auth/login", status, data, 200)
        if status == 200:
            assert "access_token" in data
            self.auth_token = data["access_token"]

    async def test_auth_me(self):
        if not self.auth_token:
            await self.test_auth_login()

        status, data = await self.request("GET", "/auth/me")
        self.print_result("GET /auth/me", status, data, 200)
        if status == 200:
            assert "id" in data
            assert "email" in data

    async def test_auth_invalid_token(self):
        old_token = self.auth_token
        self.auth_token = "invalid.token.here"
        status, data = await self.request("GET", "/auth/me")
        self.print_result("GET /auth/me (invalid token)", status, data, 401)
        self.auth_token = old_token

    # ==================== TRUSTED CONTACTS ====================

    async def test_trusted_contacts_crud(self):
        if not self.auth_token:
            await self.test_auth_login()

        # Create
        payload = {
            "name": "Jane Doe",
            "phone_number": "+15559876543",
            "relation": "sister",
        }
        status, data = await self.request("POST", "/trusted-contacts", json=payload)
        self.print_result("POST /trusted-contacts", status, data, 201)
        if status == 201:
            self.contact_id = data["id"]
            print(f"   → Created contact: {self.contact_id}")

        # List
        status, data = await self.request("GET", "/trusted-contacts")
        self.print_result("GET /trusted-contacts", status, data, 200)
        if status == 200:
            assert isinstance(data, list)

        # Get single
        if self.contact_id:
            status, data = await self.request("GET", f"/trusted-contacts/{self.contact_id}")
            self.print_result(f"GET /trusted-contacts/{self.contact_id[:8]}...", status, data, 200)

        # Delete
        if self.contact_id:
            status, data = await self.request("DELETE", f"/trusted-contacts/{self.contact_id}")
            self.print_result(f"DELETE /trusted-contacts/{self.contact_id[:8]}...", status, data, 204)

    # ==================== SAFE WALK ====================

    async def test_safe_walk_session(self):
        if not self.auth_token:
            await self.test_auth_login()

        # Start session
        payload = {
            "destination": {"lat": 40.7829, "lon": -73.9654},
            "expected_arrival_minutes": 30,
        }
        status, data = await self.request("POST", "/safe-walk/start", json=payload)
        self.print_result("POST /safe-walk/start", status, data, 201)
        if status == 201:
            self.session_id = data["id"]
            print(f"   → Session: {self.session_id}, status: {data['status']}")

        # Update location
        if self.session_id:
            payload = {"location": {"lat": 40.7600, "lon": -73.9800}}
            status, data = await self.request("POST", f"/safe-walk/{self.session_id}/update", json=payload)
            self.print_result(f"POST /safe-walk/{self.session_id[:8]}.../update", status, data, 200)

        # Get active
        status, data = await self.request("GET", "/safe-walk/active")
        self.print_result("GET /safe-walk/active", status, data, 200)

        # Get specific
        if self.session_id:
            status, data = await self.request("GET", f"/safe-walk/{self.session_id}")
            self.print_result(f"GET /safe-walk/{self.session_id[:8]}...", status, data, 200)

        # Stop session
        if self.session_id:
            status, data = await self.request("POST", f"/safe-walk/{self.session_id}/stop")
            self.print_result(f"POST /safe-walk/{self.session_id[:8]}.../stop", status, data, 200)
            if status == 200:
                assert data["status"] == "ended"

    # ==================== REPORTS ====================

    async def test_reports(self):
        # Submit anonymous report
        payload = {
            "location": {"lat": 40.7580, "lon": -73.9855},
            "report_type": "poor_lighting",
            "description": "Streetlight out on 42nd St",
        }
        status, data = await self.request("POST", "/report", json=payload)
        self.print_result("POST /report (anonymous)", status, data, 201)
        report_id = data.get("id") if status == 201 else None

        # Submit authenticated report
        if not self.auth_token:
            await self.test_auth_login()
        payload = {
            "location": {"lat": 38.8977, "lon": -77.0365},
            "report_type": "broken_sidewalk",
            "description": "Cracked pavement near White House",
        }
        status, data = await self.request("POST", "/report", json=payload)
        self.print_result("POST /report (authenticated)", status, data, 201)

        # Get nearby reports
        status, data = await self.request(
            "GET", "/reports/nearby", params={"lat": 40.7580, "lon": -73.9855, "radius_m": 1000}
        )
        self.print_result("GET /reports/nearby", status, data, 200)
        if status == 200:
            assert isinstance(data, list)
            print(f"   → Found {len(data)} nearby reports")

    # ==================== RUN ALL ====================

    async def run_all(self):
        print("=" * 60)
        print("SafeWalk API Manual Test Suite")
        print(f"Base URL: {self.base_url}")
        print("=" * 60)

        tests = [
            ("Health Check", self.test_health),
            ("Geocoding", self.test_geocode),
            ("Reverse Geocoding", self.test_reverse_geocode),
            ("Route - Basic", self.test_route_basic),
            ("Route - Alternatives", self.test_route_with_alternatives),
            ("Route - Sidewalk Required", self.test_route_require_sidewalk),
            ("Route - Validation", self.test_route_validation_errors),
            ("Auth - Register", self.test_auth_register),
            ("Auth - Login", self.test_auth_login),
            ("Auth - Me", self.test_auth_me),
            ("Auth - Invalid Token", self.test_auth_invalid_token),
            ("Trusted Contacts CRUD", self.test_trusted_contacts_crud),
            ("Safe Walk Session", self.test_safe_walk_session),
            ("Reports", self.test_reports),
        ]

        passed = 0
        failed = 0

        for name, test_fn in tests:
            try:
                await test_fn()
                passed += 1
            except Exception as e:
                print(f"\n❌ {name} — ERROR: {e}")
                failed += 1

        print("\n" + "=" * 60)
        print(f"Results: {passed} passed, {failed} failed")
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description="Test SafeWalk API endpoints")
    parser.add_argument(
        "--base-url",
        default="https://safewalk-backend-l7a7.onrender.com/api/v1",
        help="Base API URL (default: Render deployment)",
    )
    args = parser.parse_args()

    tester = SafeWalkAPITester(args.base_url)
    try:
        await tester.run_all()
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
