# Clinical Unit Backend

Clinical Unit Backend is a Python FastAPI application for managing patient data in a clinical rounding system. It integrates with Azure Cosmos DB for data storage, Azure OpenAI for AI-powered summarization, and Azure AD for authentication.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap and Dependencies
- Install Python dependencies:
  ```bash
  pip install -r requirements.txt
  ```
  **TIMING**: Takes 4-5 minutes. NEVER CANCEL. Set timeout to 10+ minutes.

### Environment Setup
- Copy environment template:
  ```bash
  cp .env.sample .env
  ```
- For development mode (bypasses authentication):
  ```bash
  export DEVELOPMENT_MODE=true
  ```

### Development Server
- Start development server (with auto-reload):
  ```bash
  fastapi dev ./src/main.py
  ```
  **TIMING**: Starts in 2-3 seconds. Runs on http://127.0.0.1:8000

### Production Server  
- Start production server:
  ```bash
  fastapi run ./src/main.py --port 5000
  ```
  **TIMING**: Starts in 2-3 seconds. Runs on http://0.0.0.0:5000

### Load Sample Data
- Load patient data (requires server running):
  ```bash
  echo "y" | python ./src/load_patients.py patients.json
  ```
  **TIMING**: Takes 10-15 seconds for 10 patients. Works in development mode without authentication.

### Docker (Limited Support)
- Docker build works locally but may fail in sandboxed environments due to SSL certificate issues:
  ```bash
  docker build -t clinical-rounds-be .
  ```
  **NOTE**: If docker build fails with SSL errors, this is expected in sandboxed environments. Use local Python installation instead.

## Validation

### Manual Testing Scenarios
1. **Health Check**:
   ```bash
   curl -s http://127.0.0.1:8000/
   # Expected: {"message": "Hello World"}
   ```

2. **Patient Data Workflow** (Development Mode):
   ```bash
   # Start server in development mode
   DEVELOPMENT_MODE=true fastapi dev ./src/main.py
   
   # Load sample data (in another terminal)
   echo "y" | python ./src/load_patients.py patients.json
   
   # Test retrieving patient data
   curl -s http://127.0.0.1:8000/api/patient/P001
   # Expected: Patient data or mock error message
   
   # Test saving new patient
   curl -s -X POST http://127.0.0.1:8000/api/patient \
     -H "Content-Type: application/json" \
     -d '{"mrn": "TEST001", "name": "Test Patient", "age": 45}'
   # Expected: {"status": "patient data saved", "mrn": "TEST001"}
   
   # Test summarization
   curl -s -X POST http://127.0.0.1:8000/api/summarize \
     -H "Content-Type: application/json" \
     -d '{"patient_id": "P001"}'
   # Expected: {"detail": "Accepted for processing"}
   ```

3. **API Documentation**:
   - Visit http://127.0.0.1:8000/docs for interactive Swagger documentation

### Code Validation
- Validate Python syntax:
  ```bash
  python -m py_compile src/*.py
  ```

## Authentication & Production

### Development Mode
- Set `DEVELOPMENT_MODE=true` to bypass Azure AD authentication
- Uses mock database when Azure Cosmos DB is not configured
- All endpoints work without Bearer tokens

### Production Mode  
- Requires Azure AD JWT tokens for all `/api/*` endpoints
- Requires Azure Cosmos DB configuration in `.env`:
  ```
  COSMOSDB_DATABASE=your_database
  COSMOSDB_COLLECTION=your_collection  
  COSMOSDB_USERNAME=your_username
  COSMOSDB_PASSWORD=your_password
  COSMOSDB_HOST=your_host
  ```

### Azure Deployment
- Deploy with Azure Developer CLI:
  ```bash
  azd auth login
  az login --use-device-code
  azd up
  ```
  **TIMING**: Full deployment takes 15-20 minutes. NEVER CANCEL. Set timeout to 30+ minutes.

## Project Structure

### Key Files
- `src/main.py` - FastAPI application entry point
- `src/auth_middleware.py` - Azure AD JWT authentication  
- `src/cosmosdb_helper.py` - Azure Cosmos DB operations
- `src/summarizer.py` - AI-powered patient summarization
- `src/load_patients.py` - Utility script for loading sample data
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration
- `azure.yaml` - Azure deployment configuration

### API Endpoints
- `GET /` - Health check (no auth required)
- `GET /api/patient/{id}` - Retrieve patient data (auth required in production)
- `POST /api/patient` - Save patient data (auth required in production)  
- `POST /api/summarize` - Request patient summarization (auth required in production)

### Sample Data
- `patients.json` contains 10 sample patients (P001-P010)
- Each patient has: MRN, name, demographics, predictions, notes, vitals

## Common Tasks

### Add New API Endpoint
1. Add route function to `src/main.py`
2. Include authentication dependency: `current_user: Dict[str, Any] = Depends(get_current_user_conditional)`
3. Test manually with curl commands
4. Update this documentation

### Modify Patient Data Structure
1. Update models in `src/main.py` 
2. Update `cosmosdb_helper.py` if needed
3. Regenerate sample data in `patients.json`
4. Test with load_patients.py script

### Debug Authentication Issues
1. Set `DEVELOPMENT_MODE=true` to bypass auth
2. Check Azure AD token with: https://jwt.ms
3. Verify environment variables are set correctly
4. Test with Swagger UI at /docs

## Repository Quick Reference

### Repository Root Structure
```
.
├── README.md
├── requirements.txt  
├── Dockerfile
├── docker-compose.yml
├── azure.yaml
├── .env.sample
├── patients.json
├── src/
│   ├── main.py
│   ├── auth_middleware.py
│   ├── cosmosdb_helper.py
│   ├── summarizer.py
│   ├── load_patients.py
│   └── telemetry.py
├── infra/
│   ├── main.bicep
│   └── hooks/
└── test.http
```

### Environment Variables (.env)
```bash
# Required for Azure deployment
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT_NAME=
COSMOSDB_DATABASE=
COSMOSDB_COLLECTION=
COSMOSDB_USERNAME=
COSMOSDB_PASSWORD=
COSMOSDB_HOST=

# Optional for development
DEVELOPMENT_MODE=true
REQUIRE_DATABASE=false
```