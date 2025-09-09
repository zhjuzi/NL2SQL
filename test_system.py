#!/usr/bin/env python3
"""
Test script for the NL2SQL system
"""

import requests
import json
import time
from typing import Dict, Any

# API base URL
BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        result = response.json()
        print(f"Health status: {result}")
        return result.get("status") == "healthy"
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_tables_endpoint():
    """Test the tables endpoint"""
    print("\nTesting tables endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/schema/tables")
        result = response.json()
        print(f"Available tables: {result.get('tables', [])}")
        return True
    except Exception as e:
        print(f"Tables endpoint failed: {e}")
        return False

def test_simple_query(query: str):
    """Test a simple natural language query"""
    print(f"\nTesting query: '{query}'")
    try:
        payload = {
            "question": query,
            "max_retries": 3
        }
        
        response = requests.post(
            f"{BASE_URL}/query",
            json=payload,
            timeout=30  # 30 second timeout
        )
        
        result = response.json()
        
        print(f"Success: {result.get('success')}")
        print(f"SQL Query: {result.get('sql_query')}")
        print(f"Retry count: {result.get('retry_count', 0)}")
        
        if result.get('success'):
            print(f"Results count: {len(result.get('results', []))}")
            if result.get('results'):
                print(f"First result: {result['results'][0] if result['results'] else 'No results'}")
        else:
            print(f"Error: {result.get('error')}")
        
        return result.get('success')
    
    except Exception as e:
        print(f"Query test failed: {e}")
        return False

def test_chinese_query():
    """Test a Chinese language query"""
    print("\nTesting Chinese query...")
    chinese_query = "显示所有表格"
    return test_simple_query(chinese_query)

def run_all_tests():
    """Run all tests"""
    print("=== NL2SQL System Test Suite ===")
    print(f"Testing API at: {BASE_URL}")
    print()
    
    tests = [
        ("Health Check", test_health_check),
        ("Tables Endpoint", test_tables_endpoint),
        ("Simple Query", lambda: test_simple_query("Show me all tables")),
        ("Chinese Query", test_chinese_query),
        ("Count Query", lambda: test_simple_query("Count all records in users table")),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            success = test_func()
            results.append((test_name, success))
            print(f"Result: {'✓ PASS' if success else '✗ FAIL'}")
        except Exception as e:
            print(f"Result: ✗ ERROR - {e}")
            results.append((test_name, False))
        
        time.sleep(1)  # Small delay between tests
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print('='*50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        print(f"{test_name}: {'✓ PASS' if success else '✗ FAIL'}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == "__main__":
    print("Make sure the NL2SQL server is running on port 8000")
    print("You can start it with: python main.py")
    print()
    
    input("Press Enter to continue with tests...")
    
    success = run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Some tests failed. Check the logs above.")
    
    exit(0 if success else 1)