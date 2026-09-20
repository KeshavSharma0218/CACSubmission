"""
Run this locally to see actual 500 error details from Render.
"""
import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def debug():
    base_url = 'https://safewalk-backend-l7a7.onrender.com/api/v1'
    # Or get from env
    # base_url = os.getenv("RENDER_API_URL", "https://safewalk-backend-l7a7.onrender.com/api/v1")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Register
        email = f"debug_{int(asyncio.get_event_loop().time())}@example.com"
        resp = await client.post(f'{base_url}/auth/register', json={
            'email': email,
            'password': 'TestPass123!',
            'display_name': 'Debug User'
        })
        print(f"Register: {resp.status_code}")
        if resp.status_code != 201:
            print(f"  Error: {resp.text}")
            return
        
        data = resp.json()
        token = data['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        print(f"  Token: {token[:20]}...")
        
        # Test safe-walk/start
        print("\n--- Testing /safe-walk/start ---")
        resp = await client.post(f'{base_url}/safe-walk/start', json={
            'start_location': {'lat': 40.757, 'lon': -73.985},
            'destination': {'lat': 40.7829, 'lon': -73.9654},
            'expected_arrival_at': '2026-09-21T00:00:00+00:00'
        }, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        # Test reports
        print("\n--- Testing /reports ---")
        resp = await client.post(f'{base_url}/reports', json={
            'location': {'lat': 40.7580, 'lon': -73.9855},
            'report_type': 'poor_lighting',
            'description': 'Dark street'
        }, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        # Test reports/report (alias)
        print("\n--- Testing /reports/report ---")
        resp = await client.post(f'{base_url}/reports/report', json={
            'location': {'lat': 40.7580, 'lon': -73.9855},
            'report_type': 'broken_sidewalk',
            'description': 'Cracked pavement'
        }, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        # Test nearby
        print("\n--- Testing /reports/nearby ---")
        resp = await client.get(f'{base_url}/reports/nearby?lat=40.7580&lon=-73.9855&radius_m=1000')
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")

if __name__ == "__main__":
    asyncio.run(debug())
