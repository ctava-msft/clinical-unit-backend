"""
Simple tests for the Role Management System

These tests validate the basic functionality of the role management endpoints
in development mode. They can be run manually to verify the system works correctly.
"""

import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def print_test_result(test_name: str, success: bool, message: str = ""):
    """Print formatted test result"""
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"{status}: {test_name}")
    if message:
        print(f"    {message}")

def test_get_all_roles():
    """Test retrieving all available clinical roles"""
    response = requests.get(f"{BASE_URL}/api/roles")
    success = response.status_code == 200
    
    if success:
        roles = response.json()
        expected_roles = ["physician", "nurse", "case_manager"]
        actual_roles = [role["role"] for role in roles]
        success = all(role in actual_roles for role in expected_roles)
        message = f"Found {len(roles)} roles: {actual_roles}" if success else f"Expected {expected_roles}, got {actual_roles}"
    else:
        message = f"HTTP {response.status_code}: {response.text}"
    
    print_test_result("Get all roles", success, message)
    return success

def test_get_specific_role():
    """Test retrieving a specific role"""
    response = requests.get(f"{BASE_URL}/api/roles/physician")
    success = response.status_code == 200
    
    if success:
        role = response.json()
        success = role["role"] == "physician" and "responsibilities" in role
        message = f"Physician role has {len(role.get('responsibilities', []))} responsibilities"
    else:
        message = f"HTTP {response.status_code}: {response.text}"
    
    print_test_result("Get specific role", success, message)
    return success

def test_invalid_role():
    """Test retrieving an invalid role"""
    response = requests.get(f"{BASE_URL}/api/roles/invalid_role")
    success = response.status_code == 422  # Validation error expected
    message = "Correctly rejected invalid role" if success else f"Expected 422, got {response.status_code}"
    
    print_test_result("Get invalid role", success, message)
    return success

def test_current_user_roles_empty():
    """Test getting current user roles when no roles assigned"""
    response = requests.get(f"{BASE_URL}/api/user/roles")
    success = response.status_code == 200
    
    if success:
        user_info = response.json()
        success = user_info["user_id"] == "dev-user" and len(user_info["roles"]) >= 0
        message = f"Dev user has {len(user_info['roles'])} roles"
    else:
        message = f"HTTP {response.status_code}: {response.text}"
    
    print_test_result("Get current user roles", success, message)
    return success

def test_assign_roles():
    """Test assigning roles to a user"""
    payload = {
        "user_id": "test-user-1",
        "roles": ["physician", "nurse"]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/user/roles",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    success = response.status_code == 200
    
    if success:
        result = response.json()
        success = result["status"] == "roles assigned successfully"
        message = f"Assigned {len(payload['roles'])} roles to {payload['user_id']}"
    else:
        message = f"HTTP {response.status_code}: {response.text}"
    
    print_test_result("Assign user roles", success, message)
    return success

def test_get_user_roles_by_id():
    """Test getting roles for a specific user"""
    response = requests.get(f"{BASE_URL}/api/user/test-user-1/roles")
    success = response.status_code == 200
    
    if success:
        user_info = response.json()
        success = user_info["user_id"] == "test-user-1" and len(user_info["roles"]) == 2
        message = f"User test-user-1 has {len(user_info['roles'])} roles"
    else:
        message = f"HTTP {response.status_code}: {response.text}"
    
    print_test_result("Get user roles by ID", success, message)
    return success

def test_assign_case_manager_role():
    """Test assigning case manager role specifically"""
    payload = {
        "user_id": "case-manager-test",
        "roles": ["case_manager"]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/user/roles",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    success = response.status_code == 200
    
    if success:
        # Verify the role was assigned
        verify_response = requests.get(f"{BASE_URL}/api/user/case-manager-test/roles")
        if verify_response.status_code == 200:
            user_info = verify_response.json()
            success = (len(user_info["roles"]) == 1 and 
                      user_info["roles"][0]["role"] == "case_manager")
            message = f"Case manager role assigned and verified"
        else:
            success = False
            message = "Assignment succeeded but verification failed"
    else:
        message = f"HTTP {response.status_code}: {response.text}"
    
    print_test_result("Assign case manager role", success, message)
    return success

def test_invalid_role_assignment():
    """Test that invalid role assignment is rejected"""
    payload = {
        "user_id": "invalid-test",
        "roles": ["invalid_role"]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/user/roles",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    success = response.status_code == 422  # Validation error expected
    message = "Correctly rejected invalid role assignment" if success else f"Expected 422, got {response.status_code}"
    
    print_test_result("Invalid role assignment", success, message)
    return success

def run_all_tests():
    """Run all role management tests"""
    print("🧪 Running Role Management Tests")
    print("=" * 50)
    
    tests = [
        test_get_all_roles,
        test_get_specific_role,
        test_invalid_role,
        test_current_user_roles_empty,
        test_assign_roles,
        test_get_user_roles_by_id,
        test_assign_case_manager_role,
        test_invalid_role_assignment
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print_test_result(test_func.__name__, False, f"Exception: {str(e)}")
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print(f"❌ {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test runner error: {str(e)}")
        sys.exit(1)