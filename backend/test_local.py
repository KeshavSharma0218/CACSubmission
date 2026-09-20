#!/usr/bin/env python3
"""
Local integration test - run against local or deployed API.
Usage: python test_local.py [--base-url URL]
Default base URL: http://localhost:8000/api/v1
"""
import argparse
import asyncio
import httpx
from datetime import datetime, timezone, timedelta


async def test_endpoint(name: str, method: str, path: str, expected: int, client: httpx.AsyncClient, base_url: str, **kwargs):
    try:
        resp = await client.request(method, f"{base_url}{path}", **kwargs)
        status = "✅" if resp.status_code == expected else "❌"
        print(f"{status} {method} {path} → {resp.status_code} (expected {expected})")
        if resp.status_code != expected:
            print(f"   Response: {resp.text[:200]}")
        return resp.status_code == expected, resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
    except Exception as e:
        print(f"❌ {method} {path} → ERROR: {e}")
        return False, str(e)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1", help="Base API URL")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print("=" * 60)
    print("SafeWalk Integration Test")
    print(f"Base URL: {base_url}")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        results = []
        
        # 1. Health check
        print("\n--- System ---")
        ok, data = await test_endpoint("Health", "GET", "/health", 200, client, base_url)
        results.append(("Health", ok))
        if ok:
            print(f"   DB Connected: {data.get('database_connected')}")
            print(f"   Env: {data.get('environment')}")
        
        # 2. Geocoding
        print("\n--- Geocoding ---")
        ok, data = await test_endpoint("Geocode", "GET", "/geocode?address=Times%20Square%20NYC", 200, client, base_url)
        results.append(("Geocode", ok))
        if ok:
            coord = data.get("coordinate", {})
            print(f"   → {coord.get('lat')}, {coord.get('lon')}")
            TEST_START = coord
        
        ok, data = await test_endpoint("Reverse Geocode", "GET", "/reverse-geocode?lat=40.7580&lon=-73.9855", 200, client, base_url)
        results.append(("Reverse Geocode", ok))
        if ok:
            print(f"   → {data.get('address')[:60]}...")
        
        # 3. Routing
        print("\n--- Routing ---")
        if 'TEST_START' in locals():
            payload = {
                "start": TEST_START,
                "destination": {"lat": 40.7829, "lon": -73.9654},
                "preference": "safest",
                "require_sidewalk": False,
            }
            ok, data = await test_endpoint("Route (safest)", "POST", "/route", 200, client, base_url, json=payload)
            results.append(("Route", ok))
            if ok:
                print(f"   Safety: {data.get('safety_score'):.2f}")
                print(f"   Distance: {data.get('distance_m'):.0f}m")
                print(f"   Warnings: {data.get('warnings')}")
        
        # 4. Auth
        print("\n--- Auth ---")
        import time
        email = f"test_{int(time.time())}@example.com"
        ok, data = await test_endpoint("Register", "POST", "/auth/register", 201, client, base_url, json={
            "email": email,
            "password": "TestPass123!",
            "display_name": "Test User",
        })
        results.append(("Register", ok))
        token = None
        if ok:
            token = data.get("access_token")
            print(f"   Token: {token[:20]}...")
        
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            ok, data = await test_endpoint("Login", "POST", "/auth/login", 200, client, base_url, json={
                "email": email,
                "password": "TestPass123!",
            })
            results.append(("Login", ok))
            
            ok, data = await test_endpoint("Me", "GET", "/auth/me", 200, client, base_url, headers=headers)
            results.append(("Me", ok))
            
            # 5. Trusted Contacts
            print("\n--- Trusted Contacts ---")
            ok, data = await test_endpoint("Create Contact", "POST", "/trusted-contacts", 201, client, base_url, 
                json={"name": "Jane", "phone_number": "+15551234567", "relation": "sister"}, headers=headers)
            results.append(("Create Contact", ok))
            contact_id = data.get("id") if ok else None
            
            ok, data = await test_endpoint("List Contacts", "GET", "/trusted-contacts", 200, client, base_url, headers=headers)
            results.append(("List Contacts", ok))
            
            if contact_id:
                ok, data = await test_endpoint("Delete Contact", "DELETE", f"/trusted-contacts/{contact_id}", 204, client, base_url, headers=headers)
                results.append(("Delete Contact", ok))
            
            # 6. Safe Walk
            print("\n--- Safe Walk ---")
            if 'TEST_START' in locals():
                start_time = datetime.now(timezone.utc) + timedelta(minutes=1)
                ok, data = await test_endpoint("Start Walk", "POST", "/safe-walk/start", 201, client, base_url,
                    json={
                        "start_location": TEST_START,
                        "destination": {"lat": 40.7829, "lon": -73.9654},
                        "expected_arrival_at": start_time.isoformat()
                    }, headers=headers)
                results.append(("Start Walk", ok))
                session_id = data.get("id") if ok else None
                
                if session_id:
                    ok, data = await test_endpoint("Update Location", "POST", f"/safe-walk/{session_id}/update", 200, client, base_url,
                        json={"location": {"lat": 40.7600, "lon": -73.9800}}, headers=headers)
                    results.append(("Update Location", ok))
                    
                    ok, data = await test_endpoint("Active Walk", "GET", "/safe-walk/active", 200, client, base_url, headers=headers)
                    results.append(("Active Walk", ok))
                    
                    ok, data = await test_endpoint("Stop Walk", "POST", f"/safe-walk/{session_id}/stop", 200, client, base_url, headers=headers)
                    results.append(("Stop Walk", ok))
            
            # 7. Reports
            print("\n--- Reports ---")
            ok, data = await test_endpoint("Create Report (auth)", "POST", "/reports", 201, client, base_url,
                json={"location": {"lat": 40.7580, "lon": -73.9855}, "report_type": "poor_lighting", "description": "Dark street"}, headers=headers)
            results.append(("Create Report (auth)", ok))
            
            ok, data = await test_endpoint("Create Report (anon)", "POST", "/reports/report", 201, client, base_url,
                json={"location": {"lat": 40.7580, "lon": -73.9855}, "report_type": "broken_sidewalk", "description": "Cracked pavement"})
            results.append(("Create Report (anon)", ok))
            
            ok, data = await test_endpoint("Nearby Reports", "GET", "/reports/nearby?lat=40.7580&lon=-73.9855&radius_m=1000", 200, client, base_url)
            results.append(("Nearby Reports", ok))
            if ok:
                print(f"   Found {len(data)} nearby reports")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        passed = sum(1 for _, ok in results if ok)
        total = len(results)
        for name, ok in results:
            status = "✅" if ok else "❌"
            print(f"  {status} {name}")
        print(f"\nTotal: {passed}/{total} passed")
        
        if passed == total:
            print("\n🎉 All tests passed! Ready for deployment.")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed. Check logs above.")
        
        return passed == total


if __name__ == "__main__":
    asyncio.run(main())
