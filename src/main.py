"""
Clinical Rounds Backend API

This FastAPI application provides endpoints for managing patient data and generating
clinical summaries a clinical rounding system. It integrates with:
- Azure Cosmos DB for patient data storage
- OpenAI/Azure OpenAI for AI-powered summarization
- Application Insights for telemetry and monitoring
"""

import os
from pathlib import Path
# FastAPI framework and dependencies for building REST API
from fastapi import FastAPI, BackgroundTasks, Request, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# Environment variable management
from dotenv import load_dotenv
# Prompty framework for AI prompt management and tracing
from prompty.tracer import trace
from prompty.core import PromptyStream, AsyncPromptyStream
# FastAPI response types and middleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
# OpenTelemetry instrumentation for monitoring
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import FastAPI, Body
# Pydantic for data validation
from pydantic import BaseModel
# URL encoding for database connection strings
from urllib.parse import quote_plus
# Custom modules for database operations and AI summarization
import cosmosdb_helper
import summarizer
from auth_middleware import get_current_user, get_current_user_from_request, require_auth, get_user_from_request, extract_token_from_request
from role_service import RoleService
from models import ClinicalRole, RoleInfo, AssignRoleRequest, UserRoleResponse
from typing import Dict, Any, List

# Task model for background processing
class Task(BaseModel):
    id: str

# Custom telemetry setup module
from telemetry import setup_telemetry

# Get the base directory for the application
base = Path(__file__).resolve().parent

# Load environment variables from .env file - check multiple locations
env_loaded = False

# Try to load .env from the parent directory (where it actually is)
env_file_parent = base.parent / ".env"
if env_file_parent.exists():
    load_dotenv(env_file_parent)
    env_loaded = True
    #print(f"✓ Loaded .env from: {env_file_parent}")
else:
    # Try to load from current directory
    env_file_current = base / ".env"
    if env_file_current.exists():
        load_dotenv(env_file_current)
        env_loaded = True
        #print(f"✓ Loaded .env from: {env_file_current}")
    else:
        # Last try - default load_dotenv behavior
        load_dotenv()
        #print("⚠ Using default load_dotenv() - checking current working directory")

if not env_loaded:
    print("⚠ No .env file found in expected locations:")
    print(f"  - {env_file_parent}")
    print(f"  - Current working directory: {Path.cwd()}")

# Debug: Print environment variable status
#print("\nEnvironment Variables Status:")
cosmosdb_vars = [
    "COSMOSDB_DATABASE",
    "COSMOSDB_COLLECTION", 
    "COSMOSDB_USERNAME",
    "COSMOSDB_PASSWORD",
    "COSMOSDB_HOST"
]

for var in cosmosdb_vars:
    value = os.getenv(var)
    status = "✓" if value else "✗"
    #print(f"  {var}: {status} {'(set)' if value else '(not set)'}")

# Initialize FastAPI application
app = FastAPI()

# Control whether we allow fallback to an in-memory/mock database
REQUIRE_DATABASE = os.getenv("REQUIRE_DATABASE", "false").lower() in ("true", "1", "yes", "on")

# Azure Cosmos DB configuration with better error handling
try:
    database = os.getenv("COSMOSDB_DATABASE")
    container = os.getenv("COSMOSDB_COLLECTION")
    username = os.getenv("COSMOSDB_USERNAME", "")
    password = os.getenv("COSMOSDB_PASSWORD", "")
    host = os.getenv("COSMOSDB_HOST", "")
    options = os.getenv("COSMOSDB_OPTIONS", "")
    
    # Check if any are None or empty
    if not database:
        raise ValueError("COSMOSDB_DATABASE environment variable is required")
    if not container:
        raise ValueError("COSMOSDB_COLLECTION environment variable is required")
    if not username:
        raise ValueError("COSMOSDB_USERNAME environment variable is required")
    if not password:
        raise ValueError("COSMOSDB_PASSWORD environment variable is required")
    if not host:
        raise ValueError("COSMOSDB_HOST environment variable is required")
    
    # Clean the values
    database = database.strip('" ')
    container = container.strip('" ')
    username = quote_plus(username.strip('" '))
    password = quote_plus(password.strip('" '))
    host = host.strip('" ')
    options = options.strip('" ')

    # Build MongoDB connection string for Cosmos DB API compatibility
    connection_string = f"mongodb://{username}:{password}@{host}:10255/?ssl=true&replicaSet=globaldb&retryWrites=false&maxIdleTimeMS=120000"

    # Initialize Cosmos DB helper with connection details
    cosmosDBHelper = cosmosdb_helper.CosmosDBHelper(connection_string, database, container)

    # Initialize AI summarizer with database helper
    summarizer = summarizer.Summarizer(cosmosDBHelper)
    
    # Initialize role service with database helper
    role_service = RoleService(cosmosDBHelper)
    
    print("✓ Successfully initialized Cosmos DB, Summarizer, and Role Service")

except Exception as e:
    print(f"✗ Error initializing Cosmos DB: {e}")
    if REQUIRE_DATABASE:
        # Fail fast instead of silently using mock services
        raise RuntimeError("Database initialization failed and REQUIRE_DATABASE is set. Aborting startup.") from e
    print("Using mock services for development (set REQUIRE_DATABASE=1 to disable this fallback)...")

    class MockCosmosDBHelper:
        def __init__(self):
            # In-memory storage for mock database
            self._user_roles = {}
            
        def get_patient(self, patient_id: str):
            return {"error": f"Database not configured. Patient {patient_id} not found."}

        def save_patient_data(self, patient_id: str, patient_data: dict):
            return True

        def save_user_roles(self, user_id: str, roles: list) -> bool:
            self._user_roles[user_id] = roles
            return True

        def get_user_roles(self, user_id: str) -> list:
            return self._user_roles.get(user_id, [])

        def remove_user_roles(self, user_id: str) -> bool:
            if user_id in self._user_roles:
                del self._user_roles[user_id]
            return True

    class MockSummarizer:
        def __init__(self, db_helper):
            self.cosmosDBHelper = db_helper

        def summarize_patient(self, patient_id: str):
            return "Mock summary completed"

    cosmosDBHelper = MockCosmosDBHelper()
    summarizer = MockSummarizer(cosmosDBHelper)
    
    # Initialize role service with mock database helper
    role_service = RoleService(cosmosDBHelper)

# Get environment-specific configuration
code_space = os.getenv("CODESPACE_NAME")
app_insights = os.getenv("APPINSIGHTS_CONNECTIONSTRING")

# Configure CORS origins based on environment
if code_space: 
    # GitHub Codespaces environment - use dynamic URLs
    origin_8000= f"https://{code_space}-8000.app.github.dev"
    origin_5173 = f"https://{code_space}-5173.app.github.dev"
    ingestion_endpoint = app_insights.split(';')[1].split('=')[1] if app_insights else ""
    
    origins = [origin_8000, origin_5173, os.getenv("API_SERVICE_ACA_URI"), os.getenv("WEB_SERVICE_ACA_URI"), ingestion_endpoint]
    origins = [origin for origin in origins if origin]  # Remove None/empty values
else:
    # Production/local environment - read from origins.txt file
    try:
        origins = [
            o.strip()
            for o in Path(Path(__file__).parent / "origins.txt").read_text().splitlines()
        ]
        # Add explicit localhost origins for development
        origins.extend([
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000"
        ])
    except FileNotFoundError:
        # Fallback origins for development
        origins = [
            "http://localhost:5173",
            "http://localhost:3000", 
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "*"  # Allow all origins in development (remove in production)
        ]

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Setup telemetry and monitoring
setup_telemetry(app)

# Development mode configuration - can be controlled via environment variable
DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "false").lower() in ("true", "1", "yes", "on")
print(f"🔧 Development mode: {'ENABLED' if DEVELOPMENT_MODE else 'DISABLED'}")
if DEVELOPMENT_MODE:
    print("⚠️  WARNING: Authentication is bypassed in development mode")

# Health check endpoint
@app.get("/")
async def root():
    """Basic health check endpoint"""
    return {"message": "Hello World"}

# Optional authentication dependency for development mode
async def get_current_user_optional(request: Request) -> Dict[str, Any] | None:
    """
    Optional authentication - returns user if token is valid, None if no token or invalid
    Used in development mode for graceful degradation
    """
    try:
        token = extract_token_from_request(request)
        if not token:
            return None
        return await get_current_user_from_request(request)
    except Exception:
        return None

# Conditional authentication dependency
async def get_current_user_conditional(request: Request) -> Dict[str, Any]:
    """
    Conditional authentication based on development mode
    - Production: Requires valid authentication
    - Development: Optional authentication (allows testing without tokens)
    """
    if DEVELOPMENT_MODE:
        # In development mode, try to get user but don't fail if not authenticated
        user = await get_current_user_optional(request)
        if user:
            return user
        else:
            # Return anonymous user for development
            dev_user_id = "dev-user"
            return {
                "user_id": dev_user_id,
                "email": "dev@development.local",
                "name": "Development User",
                "tenant_id": "dev-tenant",
                "roles": role_service.get_user_roles(dev_user_id),  # Get roles from role service
                "groups": []
            }
    else:
        # Production mode - require authentication
        return await get_current_user_from_request(request)

# Patient data retrieval endpoint with conditional auth
@app.get("/api/patient/{id}")
#@trace
async def get_patient(id: str, request: Request, current_user: Dict[str, Any] = Depends(get_current_user_conditional)):
    """
    Retrieve patient data by ID from Cosmos DB
    
    Authentication is required in production, optional in development mode.

    Args:
        id (str): Patient identifier (MRN)
        request (Request): FastAPI request object
        current_user (Dict): Authenticated user information

    Returns:
        JSON: Patient data or error message
    """
    try:
        # Log access for audit trail
        user_email = current_user.get('email', 'unknown')
        is_dev_user = user_email == 'dev@development.local'
        mode_indicator = " [DEV MODE]" if is_dev_user else ""
        #print(f"Patient data access - User: {user_email}, Patient ID: {id}{mode_indicator}")
        
        patient_data = cosmosDBHelper.get_patient(id)
        # Check if patient was found
        if "error" in patient_data:
            return JSONResponse(status_code=404, content=patient_data)
        return patient_data
    except Exception as e:
        # Return server error for any unexpected exceptions
        print(f"Error retrieving patient {id}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# Patient data storage endpoint with conditional auth
@app.post("/api/patient")
async def save_patient_data(patient_data: dict, request: Request, current_user: Dict[str, Any] = Depends(get_current_user_conditional)):
    """
    Save complete patient data to the database
    
    Authentication is required in production, optional in development mode.

    Args:
        patient_data (dict): Complete patient record including MRN
        request (Request): FastAPI request object
        current_user (Dict): Authenticated user information

    Returns:
        JSON: Success confirmation or error message
    """
    try:
        # Log access for audit trail
        user_email = current_user.get('email', 'unknown')
        is_dev_user = user_email == 'dev@development.local'
        mode_indicator = " [DEV MODE]" if is_dev_user else ""
        #print(f"Patient data save - User: {user_email}{mode_indicator}")
        
        # Extract patient ID from the data
        patient_id = patient_data.get('mrn')
        if not patient_id:
            return JSONResponse(status_code=400, content={"error": "Missing mrn field in patient data"})

        # Save patient data to Cosmos DB
        cosmosDBHelper.save_patient_data(patient_id, patient_data)
        return {"status": "patient data saved", "mrn": patient_id}
    except Exception as e:
        print(f"Error saving patient data: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# Request model for patient summarization
class PatientRequest(BaseModel):
    patient_id: str

# Background task function for AI summarization
def summarize(patient_id: str):
    """
    Background task to generate AI-powered patient summary

    Args:
        patient_id (str): Patient identifier for summarization
    """
    summarizer.summarize_patient(patient_id)

# Patient summarization endpoint with conditional auth
@app.post("/api/summarize")
@trace
async def review(request_body: PatientRequest, background_tasks: BackgroundTasks, request: Request, current_user: Dict[str, Any] = Depends(get_current_user_conditional)):
    """
    Initiate patient data summarization as a background task
    
    Authentication is required in production, optional in development mode.

    Args:
        request_body (PatientRequest): Request containing patient_id
        background_tasks (BackgroundTasks): FastAPI background task manager
        request (Request): FastAPI request object
        current_user (Dict): Authenticated user information

    Returns:
        JSON: Acceptance confirmation (202 status)
    """
    try:
        # Log access for audit trail
        user_email = current_user.get('email', 'unknown')
        is_dev_user = user_email == 'dev@development.local'
        mode_indicator = " [DEV MODE]" if is_dev_user else ""
        #print(f"Patient summarization request - User: {user_email}, Patient ID: {request_body.patient_id}{mode_indicator}")
        
        # Add summarization task to background queue
        background_tasks.add_task(summarize, request_body.patient_id)
        return JSONResponse(content={"detail": "Accepted for processing"}, status_code=202)
    except Exception as e:
        print(f"Error in summarization request: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# Add a simple CORS preflight handler
@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle CORS preflight requests"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

# ============================================================================
# Role Management Endpoints
# ============================================================================

@app.get("/api/roles", response_model=List[RoleInfo])
async def get_all_roles():
    """
    Get all available clinical roles
    
    Returns:
        List: All clinical roles with their descriptions and responsibilities
    """
    try:
        roles = role_service.get_all_roles()
        return roles
    except Exception as e:
        print(f"Error retrieving roles: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/roles/{role}", response_model=RoleInfo)
async def get_role_info(role: ClinicalRole):
    """
    Get information for a specific clinical role
    
    Args:
        role (ClinicalRole): The clinical role to get information for
        
    Returns:
        RoleInfo: Detailed information about the role
    """
    try:
        role_info = role_service.get_role_info(role)
        if not role_info:
            return JSONResponse(status_code=404, content={"error": f"Role {role} not found"})
        return role_info
    except Exception as e:
        print(f"Error retrieving role info for {role}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/user/roles", response_model=UserRoleResponse)
async def get_current_user_roles(request: Request, current_user: Dict[str, Any] = Depends(get_current_user_conditional)):
    """
    Get the current user's role assignments
    
    Authentication is required in production, optional in development mode.
    
    Args:
        request (Request): FastAPI request object
        current_user (Dict): Authenticated user information
        
    Returns:
        UserRoleResponse: User information with assigned roles
    """
    try:
        user_id = current_user.get('user_id')
        user_email = current_user.get('email', 'unknown')
        user_name = current_user.get('name')
        
        # Get user's role information
        user_role_info = role_service.get_user_role_info(user_id)
        
        return UserRoleResponse(
            user_id=user_id,
            email=user_email,
            name=user_name,
            roles=user_role_info
        )
    except Exception as e:
        print(f"Error retrieving user roles: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/user/roles")
async def assign_user_roles(request_body: AssignRoleRequest, request: Request, current_user: Dict[str, Any] = Depends(get_current_user_conditional)):
    """
    Assign roles to a user
    
    Authentication is required in production, optional in development mode.
    Note: In a production system, this would require admin privileges.
    
    Args:
        request_body (AssignRoleRequest): Role assignment request
        request (Request): FastAPI request object
        current_user (Dict): Authenticated user information
        
    Returns:
        JSON: Success confirmation or error message
    """
    try:
        # Log access for audit trail
        user_email = current_user.get('email', 'unknown')
        is_dev_user = user_email == 'dev@development.local'
        mode_indicator = " [DEV MODE]" if is_dev_user else ""
        print(f"Role assignment request - Assigner: {user_email}, Target User: {request_body.user_id}, Roles: {request_body.roles}{mode_indicator}")
        
        # Assign roles to the user
        success = role_service.assign_roles_to_user(request_body.user_id, request_body.roles)
        
        if success:
            return {"status": "roles assigned successfully", "user_id": request_body.user_id, "roles": request_body.roles}
        else:
            return JSONResponse(status_code=400, content={"error": "Failed to assign roles"})
            
    except ValueError as e:
        print(f"Invalid role assignment: {str(e)}")
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        print(f"Error assigning roles: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/user/{user_id}/roles", response_model=UserRoleResponse)
async def get_user_roles_by_id(user_id: str, request: Request, current_user: Dict[str, Any] = Depends(get_current_user_conditional)):
    """
    Get role assignments for a specific user
    
    Authentication is required in production, optional in development mode.
    
    Args:
        user_id (str): The user identifier to get roles for
        request (Request): FastAPI request object
        current_user (Dict): Authenticated user information
        
    Returns:
        UserRoleResponse: User information with assigned roles
    """
    try:
        # Get user's role information
        user_role_info = role_service.get_user_role_info(user_id)
        
        return UserRoleResponse(
            user_id=user_id,
            email="",  # Email not available when querying by user_id
            name=None,
            roles=user_role_info
        )
    except Exception as e:
        print(f"Error retrieving roles for user {user_id}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# OpenTelemetry instrumentation setup
# TODO: fix open telemetry so it doesn't slow app so much
# Wrap this in a try-except to prevent failure if telemetry setup fails
try:
    # Instrument the FastAPI app for automatic telemetry collection
    FastAPIInstrumentor.instrument_app(app)
except Exception as e:
    print(f"Warning: OpenTelemetry instrumentation failed: {str(e)}")
