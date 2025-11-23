#!/usr/bin/env python3
"""Test script for the Excel Agent API."""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

BASE_URL = "http://localhost:8000"

def test_root():
    """Test root endpoint."""
    print("Testing root endpoint...")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_list_files():
    """Test file listing endpoint."""
    print("Testing /api/files endpoint...")
    response = requests.get(f"{BASE_URL}/api/files")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Found {len(data.get('files', []))} files")
        for file_info in data.get('files', [])[:3]:
            print(f"  - {file_info.get('name')}")
    else:
        print(f"Error: {response.text}")
    print()

def test_analyze(question: str):
    """Test analysis endpoint."""
    print(f"Testing /api/analyze endpoint...")
    print(f"Question: {question}")
    print("-" * 70)
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/analyze",
            params={"question": question},
            timeout=120  # Analysis might take time
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Intent: {result.get('intent')}")
            print(f"✓ Target File: {result.get('target_file')}")
            print(f"✓ Code Length: {len(result.get('code', ''))} characters")
            print(f"✓ Execution Success: {result.get('success')}")
            print(f"✓ Columns Used: {result.get('columns_used', [])}")
            print(f"✓ Column Report: {result.get('column_report', '')}")
            
            if result.get('output'):
                print(f"\nOutput Preview:")
                output_lines = result['output'].split('\n')[:10]
                for line in output_lines:
                    print(f"  {line}")
                if len(result['output'].split('\n')) > 10:
                    print(f"  ... ({len(result['output'].split('\n')) - 10} more lines)")
            
            if result.get('error'):
                print(f"\n⚠ Execution Error: {result.get('error')}")
        else:
            print(f"✗ Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Error: Could not connect to server. Is it running?")
        print("  Start the server with: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()

if __name__ == "__main__":
    print("=" * 70)
    print("EXCEL AGENT API TEST")
    print("=" * 70)
    print()
    
    # Test root
    test_root()
    
    # Test file listing
    test_list_files()
    
    # Test analysis
    test_questions = [
        "分析不同城市的销售情况",
        "What are the sales trends?"
    ]
    
    for question in test_questions:
        test_analyze(question)
        print("=" * 70)
        print()

