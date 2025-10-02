"""
Unit Tests for Role Management System

This module contains comprehensive unit tests for the role_service.py
and cosmosdb_helper.py role management functionality.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from role_service import RoleService
from models import ClinicalRole, RoleInfo
from cosmosdb_helper import CosmosDBHelper


class TestRoleServiceWithoutDatabase(unittest.TestCase):
    """Test RoleService functionality without database (in-memory storage)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.role_service = RoleService(cosmosdb_helper=None)
    
    def test_initialize_role_definitions(self):
        """Test that role definitions are properly initialized"""
        roles = self.role_service.get_all_roles()
        
        self.assertEqual(len(roles), 3)
        
        role_values = [role.role for role in roles]
        self.assertIn(ClinicalRole.PHYSICIAN, role_values)
        self.assertIn(ClinicalRole.REGISTERED_NURSE, role_values)
        self.assertIn(ClinicalRole.CASE_MANAGER, role_values)
    
    def test_get_all_roles_returns_list(self):
        """Test that get_all_roles returns a list of RoleInfo objects"""
        roles = self.role_service.get_all_roles()
        
        self.assertIsInstance(roles, list)
        self.assertTrue(all(isinstance(role, RoleInfo) for role in roles))
    
    def test_get_role_info_physician(self):
        """Test retrieving physician role information"""
        role_info = self.role_service.get_role_info(ClinicalRole.PHYSICIAN)
        
        self.assertIsNotNone(role_info)
        self.assertEqual(role_info.role, ClinicalRole.PHYSICIAN)
        self.assertEqual(role_info.display_name, "Physician")
        self.assertIn("Lead patient care decisions", role_info.responsibilities)
    
    def test_get_role_info_nurse(self):
        """Test retrieving nurse role information"""
        role_info = self.role_service.get_role_info(ClinicalRole.REGISTERED_NURSE)
        
        self.assertIsNotNone(role_info)
        self.assertEqual(role_info.role, ClinicalRole.REGISTERED_NURSE)
        self.assertEqual(role_info.display_name, "Registered Nurse (RN)")
        self.assertIn("Provide direct patient care", role_info.responsibilities)
    
    def test_get_role_info_case_manager(self):
        """Test retrieving case manager role information"""
        role_info = self.role_service.get_role_info(ClinicalRole.CASE_MANAGER)
        
        self.assertIsNotNone(role_info)
        self.assertEqual(role_info.role, ClinicalRole.CASE_MANAGER)
        self.assertEqual(role_info.display_name, "Case Manager")
        self.assertIn("Coordinate discharge planning", role_info.responsibilities)
    
    def test_assign_single_role_to_user(self):
        """Test assigning a single role to a user"""
        user_id = "test-user-1"
        roles = [ClinicalRole.PHYSICIAN]
        
        result = self.role_service.assign_roles_to_user(user_id, roles)
        
        self.assertTrue(result)
        assigned_roles = self.role_service.get_user_roles(user_id)
        self.assertEqual(len(assigned_roles), 1)
        self.assertEqual(assigned_roles[0], ClinicalRole.PHYSICIAN)
    
    def test_assign_multiple_roles_to_user(self):
        """Test assigning multiple roles to a user"""
        user_id = "test-user-2"
        roles = [ClinicalRole.PHYSICIAN, ClinicalRole.REGISTERED_NURSE]
        
        result = self.role_service.assign_roles_to_user(user_id, roles)
        
        self.assertTrue(result)
        assigned_roles = self.role_service.get_user_roles(user_id)
        self.assertEqual(len(assigned_roles), 2)
        self.assertIn(ClinicalRole.PHYSICIAN, assigned_roles)
        self.assertIn(ClinicalRole.REGISTERED_NURSE, assigned_roles)
    
    def test_assign_all_roles_to_user(self):
        """Test assigning all three roles to a user"""
        user_id = "test-user-3"
        roles = [ClinicalRole.PHYSICIAN, ClinicalRole.REGISTERED_NURSE, ClinicalRole.CASE_MANAGER]
        
        result = self.role_service.assign_roles_to_user(user_id, roles)
        
        self.assertTrue(result)
        assigned_roles = self.role_service.get_user_roles(user_id)
        self.assertEqual(len(assigned_roles), 3)
    
    def test_get_user_roles_no_roles_assigned(self):
        """Test getting roles for a user with no roles assigned"""
        user_id = "user-no-roles"
        
        roles = self.role_service.get_user_roles(user_id)
        
        self.assertEqual(roles, [])
        self.assertIsInstance(roles, list)
    
    def test_get_user_role_info(self):
        """Test getting detailed role information for a user"""
        user_id = "test-user-4"
        self.role_service.assign_roles_to_user(user_id, [ClinicalRole.PHYSICIAN])
        
        role_infos = self.role_service.get_user_role_info(user_id)
        
        self.assertEqual(len(role_infos), 1)
        self.assertIsInstance(role_infos[0], RoleInfo)
        self.assertEqual(role_infos[0].role, ClinicalRole.PHYSICIAN)
    
    def test_user_has_role_true(self):
        """Test checking if user has a specific role (positive case)"""
        user_id = "test-user-5"
        self.role_service.assign_roles_to_user(user_id, [ClinicalRole.CASE_MANAGER])
        
        has_role = self.role_service.user_has_role(user_id, ClinicalRole.CASE_MANAGER)
        
        self.assertTrue(has_role)
    
    def test_user_has_role_false(self):
        """Test checking if user has a specific role (negative case)"""
        user_id = "test-user-6"
        self.role_service.assign_roles_to_user(user_id, [ClinicalRole.PHYSICIAN])
        
        has_role = self.role_service.user_has_role(user_id, ClinicalRole.CASE_MANAGER)
        
        self.assertFalse(has_role)
    
    def test_user_has_any_role_true(self):
        """Test checking if user has any of specified roles (positive case)"""
        user_id = "test-user-7"
        self.role_service.assign_roles_to_user(user_id, [ClinicalRole.REGISTERED_NURSE])
        
        has_any = self.role_service.user_has_any_role(
            user_id, 
            [ClinicalRole.PHYSICIAN, ClinicalRole.REGISTERED_NURSE]
        )
        
        self.assertTrue(has_any)
    
    def test_user_has_any_role_false(self):
        """Test checking if user has any of specified roles (negative case)"""
        user_id = "test-user-8"
        self.role_service.assign_roles_to_user(user_id, [ClinicalRole.CASE_MANAGER])
        
        has_any = self.role_service.user_has_any_role(
            user_id, 
            [ClinicalRole.PHYSICIAN, ClinicalRole.REGISTERED_NURSE]
        )
        
        self.assertFalse(has_any)
    
    def test_remove_user_roles(self):
        """Test removing all roles from a user"""
        user_id = "test-user-9"
        self.role_service.assign_roles_to_user(user_id, [ClinicalRole.PHYSICIAN])
        
        result = self.role_service.remove_user_roles(user_id)
        
        self.assertTrue(result)
        roles = self.role_service.get_user_roles(user_id)
        self.assertEqual(roles, [])
    
    def test_remove_roles_from_user_without_roles(self):
        """Test removing roles from a user who has no roles"""
        user_id = "user-no-roles-to-remove"
        
        result = self.role_service.remove_user_roles(user_id)
        
        self.assertTrue(result)
    
    def test_reassign_roles_overwrites_previous(self):
        """Test that reassigning roles overwrites previous assignment"""
        user_id = "test-user-10"
        self.role_service.assign_roles_to_user(user_id, [ClinicalRole.PHYSICIAN])
        self.role_service.assign_roles_to_user(user_id, [ClinicalRole.CASE_MANAGER])
        
        roles = self.role_service.get_user_roles(user_id)
        
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0], ClinicalRole.CASE_MANAGER)


class TestRoleServiceWithDatabase(unittest.TestCase):
    """Test RoleService functionality with mocked database"""
    
    def setUp(self):
        """Set up test fixtures with mocked database"""
        self.mock_db = Mock(spec=CosmosDBHelper)
        self.role_service = RoleService(cosmosdb_helper=self.mock_db)
    
    def test_assign_roles_with_database_success(self):
        """Test assigning roles using database storage"""
        user_id = "db-test-user-1"
        roles = [ClinicalRole.PHYSICIAN]
        self.mock_db.save_user_roles.return_value = True
        
        result = self.role_service.assign_roles_to_user(user_id, roles)
        
        self.assertTrue(result)
        self.mock_db.save_user_roles.assert_called_once_with(user_id, ["physician"])
    
    def test_assign_roles_with_database_failure_fallback(self):
        """Test that role assignment falls back to in-memory on database failure"""
        user_id = "db-test-user-2"
        roles = [ClinicalRole.REGISTERED_NURSE]
        self.mock_db.save_user_roles.side_effect = Exception("Database error")
        
        result = self.role_service.assign_roles_to_user(user_id, roles)
        
        self.assertTrue(result)
        # Verify fallback to in-memory storage worked
        in_memory_roles = self.role_service._user_roles.get(user_id)
        self.assertIsNotNone(in_memory_roles)
        self.assertEqual(in_memory_roles, roles)
    
    def test_get_user_roles_from_database(self):
        """Test getting roles from database storage"""
        user_id = "db-test-user-3"
        self.mock_db.get_user_roles.return_value = ["physician", "nurse"]
        
        roles = self.role_service.get_user_roles(user_id)
        
        self.assertEqual(len(roles), 2)
        self.assertIn(ClinicalRole.PHYSICIAN, roles)
        self.assertIn(ClinicalRole.REGISTERED_NURSE, roles)
        self.mock_db.get_user_roles.assert_called_once_with(user_id)
    
    def test_get_user_roles_from_database_empty(self):
        """Test getting roles from database when user has no roles"""
        user_id = "db-test-user-4"
        self.mock_db.get_user_roles.return_value = []
        
        roles = self.role_service.get_user_roles(user_id)
        
        self.assertEqual(roles, [])
    
    def test_get_user_roles_database_failure_fallback(self):
        """Test that getting roles falls back to in-memory on database failure"""
        user_id = "db-test-user-5"
        self.mock_db.get_user_roles.side_effect = Exception("Database error")
        # Pre-populate in-memory storage
        self.role_service._user_roles[user_id] = [ClinicalRole.CASE_MANAGER]
        
        roles = self.role_service.get_user_roles(user_id)
        
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0], ClinicalRole.CASE_MANAGER)
    
    def test_get_user_roles_invalid_role_in_database(self):
        """Test that invalid roles in database are skipped"""
        user_id = "db-test-user-6"
        self.mock_db.get_user_roles.return_value = ["physician", "invalid_role", "nurse"]
        
        roles = self.role_service.get_user_roles(user_id)
        
        # Should only return valid roles
        self.assertEqual(len(roles), 2)
        self.assertIn(ClinicalRole.PHYSICIAN, roles)
        self.assertIn(ClinicalRole.REGISTERED_NURSE, roles)
    
    def test_remove_user_roles_with_database(self):
        """Test removing roles using database storage"""
        user_id = "db-test-user-7"
        self.mock_db.remove_user_roles.return_value = True
        
        result = self.role_service.remove_user_roles(user_id)
        
        self.assertTrue(result)
        self.mock_db.remove_user_roles.assert_called_once_with(user_id)
    
    def test_remove_user_roles_database_failure_fallback(self):
        """Test that removing roles falls back to in-memory on database failure"""
        user_id = "db-test-user-8"
        self.mock_db.remove_user_roles.side_effect = Exception("Database error")
        # Pre-populate in-memory storage
        self.role_service._user_roles[user_id] = [ClinicalRole.PHYSICIAN]
        
        result = self.role_service.remove_user_roles(user_id)
        
        self.assertTrue(result)
        self.assertNotIn(user_id, self.role_service._user_roles)


class TestClinicalRoleEnum(unittest.TestCase):
    """Test ClinicalRole enum values"""
    
    def test_physician_value(self):
        """Test physician role enum value"""
        self.assertEqual(ClinicalRole.PHYSICIAN.value, "physician")
    
    def test_nurse_value(self):
        """Test nurse role enum value"""
        self.assertEqual(ClinicalRole.REGISTERED_NURSE.value, "nurse")
    
    def test_case_manager_value(self):
        """Test case manager role enum value"""
        self.assertEqual(ClinicalRole.CASE_MANAGER.value, "case_manager")
    
    def test_role_from_string(self):
        """Test creating role from string value"""
        role = ClinicalRole("physician")
        self.assertEqual(role, ClinicalRole.PHYSICIAN)
    
    def test_invalid_role_from_string(self):
        """Test that invalid role string raises ValueError"""
        with self.assertRaises(ValueError):
            ClinicalRole("invalid_role")


class TestRoleInfoModel(unittest.TestCase):
    """Test RoleInfo model"""
    
    def test_role_info_creation(self):
        """Test creating a RoleInfo instance"""
        role_info = RoleInfo(
            role=ClinicalRole.PHYSICIAN,
            display_name="Test Role",
            description="Test description",
            responsibilities=["Task 1", "Task 2"]
        )
        
        self.assertEqual(role_info.role, ClinicalRole.PHYSICIAN)
        self.assertEqual(role_info.display_name, "Test Role")
        self.assertEqual(role_info.description, "Test description")
        self.assertEqual(len(role_info.responsibilities), 2)
    
    def test_role_info_responsibilities_list(self):
        """Test that responsibilities is a list"""
        role_info = RoleInfo(
            role=ClinicalRole.CASE_MANAGER,
            display_name="Case Manager",
            description="Coordinates care",
            responsibilities=["Plan discharge", "Connect resources"]
        )
        
        self.assertIsInstance(role_info.responsibilities, list)
        self.assertEqual(len(role_info.responsibilities), 2)


class TestCosmosDBHelperRoleMethods(unittest.TestCase):
    """Test CosmosDBHelper role management methods with mocks"""
    
    def setUp(self):
        """Set up test fixtures with mocked MongoDB client"""
        with patch('cosmosdb_helper.pymongo.MongoClient') as mock_client:
            # Mock the client and database
            mock_db = MagicMock()
            mock_client.return_value.__getitem__.return_value = mock_db
            mock_client.return_value.admin.command.return_value = {'ok': 1}
            
            # Create helper instance
            self.helper = CosmosDBHelper(
                "mongodb://test:27017",
                "test_db",
                "test_collection"
            )
            
            # Mock the collections
            self.mock_user_collection = MagicMock()
            self.helper.user_collection = self.mock_user_collection
    
    def test_save_user_roles_success(self):
        """Test saving user roles to database"""
        user_id = "test-user-1"
        roles = ["physician", "nurse"]
        self.mock_user_collection.replace_one.return_value = MagicMock()
        
        result = self.helper.save_user_roles(user_id, roles)
        
        self.assertTrue(result)
        self.mock_user_collection.replace_one.assert_called_once()
        
        # Verify the call arguments
        call_args = self.mock_user_collection.replace_one.call_args
        query = call_args[0][0]
        document = call_args[0][1]
        
        self.assertEqual(query, {"_id": user_id})
        self.assertEqual(document["_id"], user_id)
        self.assertEqual(document["user_id"], user_id)
        self.assertEqual(document["roles"], roles)
    
    def test_save_user_roles_failure(self):
        """Test that database error is raised when save fails"""
        user_id = "test-user-2"
        roles = ["case_manager"]
        self.mock_user_collection.replace_one.side_effect = Exception("Database error")
        
        with self.assertRaises(Exception):
            self.helper.save_user_roles(user_id, roles)
    
    def test_get_user_roles_with_roles(self):
        """Test getting user roles from database"""
        user_id = "test-user-3"
        expected_roles = ["physician", "nurse"]
        self.mock_user_collection.find_one.return_value = {
            "roles": expected_roles
        }
        
        roles = self.helper.get_user_roles(user_id)
        
        self.assertEqual(roles, expected_roles)
        self.mock_user_collection.find_one.assert_called_once_with(
            {"_id": user_id}, 
            {"_id": 0, "roles": 1}
        )
    
    def test_get_user_roles_no_roles(self):
        """Test getting user roles when user has no roles"""
        user_id = "test-user-4"
        self.mock_user_collection.find_one.return_value = None
        
        roles = self.helper.get_user_roles(user_id)
        
        self.assertEqual(roles, [])
    
    def test_get_user_roles_user_document_without_roles_field(self):
        """Test getting user roles when document exists but no roles field"""
        user_id = "test-user-5"
        self.mock_user_collection.find_one.return_value = {
            "user_id": user_id,
            "other_field": "value"
        }
        
        roles = self.helper.get_user_roles(user_id)
        
        self.assertEqual(roles, [])
    
    def test_get_user_roles_database_error(self):
        """Test that database error returns empty list"""
        user_id = "test-user-6"
        self.mock_user_collection.find_one.side_effect = Exception("Database error")
        
        roles = self.helper.get_user_roles(user_id)
        
        self.assertEqual(roles, [])
    
    def test_remove_user_roles_success(self):
        """Test removing user roles from database"""
        user_id = "test-user-7"
        self.mock_user_collection.delete_one.return_value = MagicMock(deleted_count=1)
        
        result = self.helper.remove_user_roles(user_id)
        
        self.assertTrue(result)
        self.mock_user_collection.delete_one.assert_called_once_with({"_id": user_id})
    
    def test_remove_user_roles_user_not_exists(self):
        """Test removing roles when user document doesn't exist"""
        user_id = "test-user-8"
        self.mock_user_collection.delete_one.return_value = MagicMock(deleted_count=0)
        
        result = self.helper.remove_user_roles(user_id)
        
        # Should still return True even if document didn't exist
        self.assertTrue(result)
    
    def test_remove_user_roles_database_error(self):
        """Test that database error returns False"""
        user_id = "test-user-9"
        self.mock_user_collection.delete_one.side_effect = Exception("Database error")
        
        result = self.helper.remove_user_roles(user_id)
        
        self.assertFalse(result)
    
    def test_get_user_complete_document(self):
        """Test getting complete user document"""
        user_id = "test-user-10"
        expected_doc = {
            "_id": user_id,
            "user_id": user_id,
            "roles": ["physician"],
            "other_field": "value"
        }
        self.mock_user_collection.find_one.return_value = expected_doc
        
        doc = self.helper.get_user(user_id)
        
        self.assertEqual(doc, expected_doc)
    
    def test_get_user_not_found(self):
        """Test getting user when user doesn't exist"""
        user_id = "test-user-11"
        self.mock_user_collection.find_one.return_value = None
        
        doc = self.helper.get_user(user_id)
        
        self.assertEqual(doc, {})
    
    def test_get_user_database_error(self):
        """Test that database error returns empty dict"""
        user_id = "test-user-12"
        self.mock_user_collection.find_one.side_effect = Exception("Database error")
        
        doc = self.helper.get_user(user_id)
        
        self.assertEqual(doc, {})


def run_tests():
    """Run all unit tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRoleServiceWithoutDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestRoleServiceWithDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestClinicalRoleEnum))
    suite.addTests(loader.loadTestsFromTestCase(TestRoleInfoModel))
    suite.addTests(loader.loadTestsFromTestCase(TestCosmosDBHelperRoleMethods))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code based on results
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit_code = run_tests()
    exit(exit_code)
