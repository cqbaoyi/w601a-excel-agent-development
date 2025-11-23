#!/usr/bin/env python3
"""Test script to verify frontend can connect to backend."""

import sys
import time
import requests
from pathlib import Path

def check_backend():
    """Check if backend is running."""
    try:
        response = requests.get('http://localhost:8000/', timeout=2)
        if response.status_code == 200:
            print("✓ Backend server is running on http://localhost:8000")
            return True
    except:
        pass
    print("✗ Backend server is NOT running")
    print("  Start it with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    return False

def check_frontend_deps():
    """Check if frontend dependencies are installed."""
    if Path('frontend/node_modules').exists():
        print("✓ Frontend dependencies are installed")
        return True
    else:
        print("✗ Frontend dependencies are NOT installed")
        print("  Install with: cd frontend && npm install")
        return False

def test_api_endpoints():
    """Test API endpoints that frontend uses."""
    print("\n" + "="*70)
    print("TESTING API ENDPOINTS USED BY FRONTEND")
    print("="*70)
    
    # Test file listing
    print("\n1. Testing /api/files endpoint...")
    try:
        response = requests.get('http://localhost:8000/api/files', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Found {len(data.get('files', []))} files")
        else:
            print(f"   ✗ Error: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test SSE endpoint
    print("\n2. Testing /api/analyze/stream endpoint (SSE)...")
    try:
        response = requests.get(
            'http://localhost:8000/api/analyze/stream',
            params={'question': 'What are the sales trends'},
            stream=True,
            timeout=10
        )
        if response.status_code == 200:
            print("   ✓ SSE connection established")
            # Read first few events
            event_count = 0
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('event:'):
                        event_type = line_str[6:].strip()
                        print(f"   ✓ Received event: {event_type}")
                        event_count += 1
                        if event_count >= 3:
                            break
        else:
            print(f"   ✗ Error: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

def main():
    print("="*70)
    print("FRONTEND TESTING SETUP CHECK")
    print("="*70)
    
    backend_ok = check_backend()
    frontend_ok = check_frontend_deps()
    
    if backend_ok and frontend_ok:
        test_api_endpoints()
    
    print("\n" + "="*70)
    print("TO START THE FRONTEND:")
    print("="*70)
    print("\n1. Start backend (in one terminal):")
    print("   cd /home/baoy/repos/w601a-excel-agent-development")
    print("   source venv/bin/activate")
    print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print("\n2. Start frontend (in another terminal):")
    print("   cd /home/baoy/repos/w601a-excel-agent-development/frontend")
    print("   npm run dev")
    print("\n3. Open browser to: http://localhost:3000")
    print("\n4. Test with questions like:")
    print("   - 分析不同城市的销售情况")
    print("   - What are the sales trends?")
    print("   - 查看发电日志数据")
    print("\n5. Check browser console (F12) for any errors")
    print("="*70)

if __name__ == "__main__":
    main()

