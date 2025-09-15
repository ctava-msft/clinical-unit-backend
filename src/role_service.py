"""
Role Management Service

This module provides functionality for managing clinical roles in the system,
including role definitions, user role assignments, and role-based access control.
"""

from typing import Dict, List, Optional
from models import ClinicalRole, RoleInfo, UserRole, UserRoleResponse
import json


class RoleService:
    """
    Service for managing clinical roles and user role assignments
    """
    
    def __init__(self):
        """Initialize the role service with predefined clinical roles"""
        self._role_definitions = self._initialize_role_definitions()
        # In a real system, this would be stored in a database
        # For now, we'll use in-memory storage for development
        self._user_roles: Dict[str, List[ClinicalRole]] = {}
    
    def _initialize_role_definitions(self) -> Dict[ClinicalRole, RoleInfo]:
        """
        Initialize the clinical role definitions with their responsibilities
        
        Returns:
            Dict mapping role enum to role information
        """
        return {
            ClinicalRole.PHYSICIAN: RoleInfo(
                role=ClinicalRole.PHYSICIAN,
                display_name="Physician",
                description="Leads patient care, manages life-support systems, and coordinates treatment plans",
                responsibilities=[
                    "Lead patient care decisions",
                    "Manage life-support systems",
                    "Coordinate treatment plans",
                    "Prescribe medications",
                    "Perform medical procedures",
                    "Consult with specialists"
                ]
            ),
            ClinicalRole.REGISTERED_NURSE: RoleInfo(
                role=ClinicalRole.REGISTERED_NURSE,
                display_name="Registered Nurse (RN)",
                description="Provides direct patient care, monitors vital signs, administers medications, and performs frequent assessments",
                responsibilities=[
                    "Provide direct patient care",
                    "Monitor vital signs",
                    "Administer medications",
                    "Perform frequent patient assessments",
                    "Document patient status",
                    "Coordinate with healthcare team"
                ]
            ),
            ClinicalRole.CASE_MANAGER: RoleInfo(
                role=ClinicalRole.CASE_MANAGER,
                display_name="Case Manager",
                description="Coordinates discharge planning and patient support services",
                responsibilities=[
                    "Coordinate discharge planning",
                    "Manage patient support services",
                    "Facilitate care transitions",
                    "Connect patients with resources",
                    "Monitor patient outcomes",
                    "Communicate with insurance providers"
                ]
            )
        }
    
    def get_all_roles(self) -> List[RoleInfo]:
        """
        Get all available clinical roles
        
        Returns:
            List of all role information objects
        """
        return list(self._role_definitions.values())
    
    def get_role_info(self, role: ClinicalRole) -> Optional[RoleInfo]:
        """
        Get information for a specific role
        
        Args:
            role: The clinical role to get information for
            
        Returns:
            Role information or None if role not found
        """
        return self._role_definitions.get(role)
    
    def assign_roles_to_user(self, user_id: str, roles: List[ClinicalRole]) -> bool:
        """
        Assign roles to a user
        
        Args:
            user_id: The user identifier
            roles: List of roles to assign
            
        Returns:
            True if assignment was successful
        """
        # Validate that all roles exist
        for role in roles:
            if role not in self._role_definitions:
                raise ValueError(f"Invalid role: {role}")
        
        self._user_roles[user_id] = roles
        return True
    
    def get_user_roles(self, user_id: str) -> List[ClinicalRole]:
        """
        Get roles assigned to a user
        
        Args:
            user_id: The user identifier
            
        Returns:
            List of roles assigned to the user
        """
        return self._user_roles.get(user_id, [])
    
    def get_user_role_info(self, user_id: str) -> List[RoleInfo]:
        """
        Get detailed role information for a user's assigned roles
        
        Args:
            user_id: The user identifier
            
        Returns:
            List of detailed role information for user's roles
        """
        user_roles = self.get_user_roles(user_id)
        return [self._role_definitions[role] for role in user_roles if role in self._role_definitions]
    
    def user_has_role(self, user_id: str, role: ClinicalRole) -> bool:
        """
        Check if a user has a specific role
        
        Args:
            user_id: The user identifier
            role: The role to check for
            
        Returns:
            True if user has the role, False otherwise
        """
        user_roles = self.get_user_roles(user_id)
        return role in user_roles
    
    def user_has_any_role(self, user_id: str, roles: List[ClinicalRole]) -> bool:
        """
        Check if a user has any of the specified roles
        
        Args:
            user_id: The user identifier
            roles: List of roles to check for
            
        Returns:
            True if user has at least one of the roles, False otherwise
        """
        user_roles = self.get_user_roles(user_id)
        return any(role in user_roles for role in roles)
    
    def remove_user_roles(self, user_id: str) -> bool:
        """
        Remove all roles from a user
        
        Args:
            user_id: The user identifier
            
        Returns:
            True if removal was successful
        """
        if user_id in self._user_roles:
            del self._user_roles[user_id]
        return True


# Global role service instance
role_service = RoleService()