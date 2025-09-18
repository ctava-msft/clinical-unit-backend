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
from diagnostic_orchestrator import DiagnosticOrchestrator, CaseExecutionSession, ActionType, ExecutionTrace
from typing import Dict, Any, List, Optional

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
    
    # Initialize diagnostic orchestrator
    try:
        diagnostic_orchestrator = DiagnosticOrchestrator()
        print("✓ Successfully initialized Diagnostic Orchestrator")
    except Exception as e:
        print(f"⚠ Warning: Could not initialize Diagnostic Orchestrator: {e}")
        diagnostic_orchestrator = None
    
    print("✓ Successfully initialized Cosmos DB and Summarizer")

except Exception as e:
    print(f"✗ Error initializing Cosmos DB: {e}")
    if REQUIRE_DATABASE:
        # Fail fast instead of silently using mock services
        raise RuntimeError("Database initialization failed and REQUIRE_DATABASE is set. Aborting startup.") from e
    print("Using mock services for development (set REQUIRE_DATABASE=1 to disable this fallback)...")

    class MockCosmosDBHelper:
        def get_patient(self, patient_id: str):
            return {"error": f"Database not configured. Patient {patient_id} not found."}

        def save_patient_data(self, patient_id: str, patient_data: dict):
            return True

    class MockSummarizer:
        def __init__(self, db_helper):
            self.cosmosDBHelper = db_helper

        def summarize_patient(self, patient_id: str):
            return "Mock summary completed"

    cosmosDBHelper = MockCosmosDBHelper()
    summarizer = MockSummarizer(cosmosDBHelper)
    
    # Initialize diagnostic orchestrator
    try:
        diagnostic_orchestrator = DiagnosticOrchestrator()
        print("✓ Successfully initialized Diagnostic Orchestrator")
    except Exception as e:
        print(f"⚠ Warning: Could not initialize Diagnostic Orchestrator: {e}")
        diagnostic_orchestrator = None

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
            return {
                "user_id": "dev-user",
                "email": "dev@development.local",
                "name": "Development User",
                "tenant_id": "dev-tenant",
                "roles": [],
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

# Request models for diagnostic orchestration
class DiagnosticCaseRequest(BaseModel):
    case_info: str
    max_rounds: int = 10
    budget_limit: Optional[float] = None
    execution_mode: str = "unconstrained"  # "instant", "questions_only", "budgeted", "unconstrained", "ensemble"

class DiagnosticCaseResponse(BaseModel):
    case_id: str
    session_id: str
    status: str
    message: str

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

# Diagnostic Orchestration endpoints
@app.post("/api/diagnostic/case", response_model=DiagnosticCaseResponse)
async def run_diagnostic_case(
    request_body: DiagnosticCaseRequest, 
    request: Request, 
    current_user: Dict[str, Any] = Depends(get_current_user_conditional)
):
    """
    Execute a diagnostic case using the MAI-DxO multi-agent orchestrator
    
    This endpoint runs the full diagnostic orchestration process with specialized agents:
    - Dr. Hypothesis: Maintains differential diagnosis with Bayesian updates
    - Dr. Test-Chooser: Selects discriminative diagnostic tests
    - Dr. Challenger: Acts as devil's advocate, prevents anchoring bias
    - Dr. Stewardship: Enforces cost-conscious care
    - Dr. Checklist: Performs quality control and consistency checks
    
    Args:
        request_body: Case information and execution parameters
        request: FastAPI request object
        current_user: Authenticated user information
        
    Returns:
        DiagnosticCaseResponse with case execution details
    """
    if not diagnostic_orchestrator:
        return JSONResponse(
            status_code=503, 
            content={"error": "Diagnostic orchestrator not available. Check Azure OpenAI configuration."}
        )
    
    try:
        # Log access for audit trail
        user_email = current_user.get('email', 'unknown')
        is_dev_user = user_email == 'dev@development.local'
        mode_indicator = " [DEV MODE]" if is_dev_user else ""
        print(f"Diagnostic orchestration request - User: {user_email}{mode_indicator}")
        
        # Execute diagnostic case
        session = await diagnostic_orchestrator.run_diagnostic_case(
            case_info=request_body.case_info,
            max_rounds=request_body.max_rounds,
            budget_limit=request_body.budget_limit,
            execution_mode=request_body.execution_mode
        )
        
        return DiagnosticCaseResponse(
            case_id=session.case_id,
            session_id=session.session_id,
            status="completed",
            message=f"Diagnostic case completed. Final diagnosis: {session.final_diagnosis or 'No diagnosis reached'}"
        )
        
    except Exception as e:
        print(f"Error in diagnostic orchestration: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/diagnostic/case/{case_id}/summary")
async def get_diagnostic_case_summary(
    case_id: str, 
    request: Request, 
    current_user: Dict[str, Any] = Depends(get_current_user_conditional)
):
    """
    Get a summary of a completed diagnostic case
    
    Args:
        case_id: Unique identifier for the diagnostic case
        request: FastAPI request object
        current_user: Authenticated user information
        
    Returns:
        JSON summary of the diagnostic session
    """
    if not diagnostic_orchestrator:
        return JSONResponse(
            status_code=503, 
            content={"error": "Diagnostic orchestrator not available"}
        )
    
    try:
        summary = diagnostic_orchestrator.get_session_summary(case_id)
        if not summary:
            return JSONResponse(status_code=404, content={"error": "Case not found"})
        
        return summary
        
    except Exception as e:
        print(f"Error retrieving case summary: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/diagnostic/case/{case_id}/traces")
async def get_diagnostic_case_traces(
    case_id: str, 
    request: Request, 
    current_user: Dict[str, Any] = Depends(get_current_user_conditional)
):
    """
    Get detailed execution traces for a diagnostic case
    
    Returns step-by-step traces of the decision-making process with actor labels,
    agent communications, debates, and reasoning chains.
    
    Args:
        case_id: Unique identifier for the diagnostic case
        request: FastAPI request object
        current_user: Authenticated user information
        
    Returns:
        JSON array of execution traces with timestamps and actor information
    """
    if not diagnostic_orchestrator:
        return JSONResponse(
            status_code=503, 
            content={"error": "Diagnostic orchestrator not available"}
        )
    
    try:
        traces = diagnostic_orchestrator.get_session_traces(case_id)
        if not traces:
            return JSONResponse(status_code=404, content={"error": "Case not found or no traces available"})
        
        # Convert traces to JSON-serializable format
        trace_data = []
        for trace in traces:
            trace_dict = {
                "case_id": trace.case_id,
                "session_id": trace.session_id,
                "timestamp": trace.timestamp.isoformat(),
                "round_number": trace.round_number,
                "action_type": trace.action_type.value,
                "actor": trace.actor,
                "content": trace.content,
                "structured_data": trace.structured_data,
                "cost_impact": trace.cost_impact
            }
            trace_data.append(trace_dict)
        
        return {"traces": trace_data, "total_traces": len(trace_data)}
        
    except Exception as e:
        print(f"Error retrieving case traces: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/diagnostic/case/{case_id}/agent-messages")
async def get_diagnostic_agent_messages(
    case_id: str, 
    request: Request, 
    current_user: Dict[str, Any] = Depends(get_current_user_conditional)
):
    """
    Get agent communication messages for a diagnostic case
    
    Returns detailed messages between the specialized diagnostic agents during
    the chain-of-debate process.
    
    Args:
        case_id: Unique identifier for the diagnostic case
        request: FastAPI request object  
        current_user: Authenticated user information
        
    Returns:
        JSON array of agent messages with roles and structured data
    """
    if not diagnostic_orchestrator:
        return JSONResponse(
            status_code=503, 
            content={"error": "Diagnostic orchestrator not available"}
        )
    
    try:
        session = diagnostic_orchestrator.active_sessions.get(case_id)
        if not session:
            return JSONResponse(status_code=404, content={"error": "Case session not found"})
        
        # Convert agent messages to JSON-serializable format
        messages_data = []
        for message in session.agent_messages:
            message_dict = {
                "agent_role": message.agent_role,
                "timestamp": message.timestamp.isoformat(),
                "message_type": message.message_type,
                "content": message.content,
                "structured_data": message.structured_data
            }
            messages_data.append(message_dict)
        
        return {"messages": messages_data, "total_messages": len(messages_data)}
        
    except Exception as e:
        print(f"Error retrieving agent messages: {str(e)}")
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

# OpenTelemetry instrumentation setup
# TODO: fix open telemetry so it doesn't slow app so much
# Wrap this in a try-except to prevent failure if telemetry setup fails
try:
    # Instrument the FastAPI app for automatic telemetry collection
    FastAPIInstrumentor.instrument_app(app)
except Exception as e:
    print(f"Warning: OpenTelemetry instrumentation failed: {str(e)}")
