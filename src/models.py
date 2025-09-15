"""
Data models for the Clinical Rounds Application

This module defines Pydantic models for API request/response validation
and data structure consistency across the application.
"""

from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class ClinicalRole(str, Enum):
    """
    Clinical roles available in the system
    
    Each role has specific responsibilities in patient care:
    - PHYSICIAN: Leads patient care, manages life-support systems, coordinates treatment plans
    - REGISTERED_NURSE: Provides direct patient care, monitors vital signs, administers medications, performs frequent assessments
    - CASE_MANAGER: Coordinates discharge planning and patient support services
    """
    PHYSICIAN = "physician"
    REGISTERED_NURSE = "nurse"  # Using "nurse" for simplicity while maintaining RN meaning
    CASE_MANAGER = "case_manager"


class RoleInfo(BaseModel):
    """
    Role information model containing role details and responsibilities
    """
    role: ClinicalRole
    display_name: str
    description: str
    responsibilities: List[str]


class UserRole(BaseModel):
    """
    User role assignment model
    """
    user_id: str
    email: str
    roles: List[ClinicalRole]


class AssignRoleRequest(BaseModel):
    """
    Request model for assigning roles to a user
    """
    user_id: str
    roles: List[ClinicalRole]


class UserRoleResponse(BaseModel):
    """
    Response model for user role information
    """
    user_id: str
    email: str
    name: Optional[str] = None
    roles: List[RoleInfo]