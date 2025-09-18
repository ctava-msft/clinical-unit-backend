# Diagnostic Orchestrator Implementation

This basic implementation brings the Diagnostic Orchestrator pattern from Microsoft AI's research paper to the Clinical Unit Backend. The system provides AI-powered diagnostic reasoning through multi-agent coordination, following evidence-based medicine principles with cost-conscious decision making.

## 🎯 Overview

The diagnostic orchestrator system simulates a panel of specialist physicians working collaboratively to solve diagnostic cases, implementing the methodology described in "Sequential Diagnosis with Language Models" (Microsoft AI, 2025).

### Key Features

- **Multi-Agent Orchestration**: Five specialized diagnostic agents with distinct roles, one consensus coordination agent
- **Chain-of-Debate Process**: Structured deliberation between agents for consensus building
- **Cost-Aware Planning**: Budget tracking and cost-effectiveness analysis
- **Comprehensive Tracing**: Step-by-step execution logs with actor-labeled decision trails
- **Multiple Execution Modes**: From instant diagnosis to full sequential reasoning

## 🏗️ Architecture

### Specialized Agents

1. **Dr. Hypothesis** (`DrHypothesis`)
   - Maintains probability-ranked differential diagnosis
   - Updates probabilities using Bayesian reasoning
   - Tracks supporting and contradictory evidence

2. **Dr. Test-Chooser** (`DrTestChooser`)
   - Selects diagnostic tests with maximum discriminative value
   - Prioritizes high-yield investigations
   - Considers test characteristics and clinical utility

3. **Dr. Challenger** (`DrChallenger`)
   - Acts as devil's advocate to prevent cognitive bias
   - Identifies anchoring bias and tunnel vision
   - Proposes alternative diagnoses and falsifying tests

4. **Dr. Stewardship** (`DrStewardship`)
   - Enforces cost-conscious medical decision making
   - Reviews test recommendations for cost-effectiveness
   - Suggests cheaper alternatives when appropriate

5. **Dr. Checklist** (`DrChecklist`)
   - Performs quality control and consistency validation
   - Ensures systematic diagnostic approach
   - Flags logical inconsistencies or gaps

6. **Consensus Coordinator** (`ConsensusCoordinator`)
   - Synthesizes all panel recommendations into unified decisions
   - Weighs evidence from each specialist to determine next action
      - Diagnostic confidence threshold set at ≥85%
   - Forces diagnosis on final rounds when confidence thresholds are met
   - Provides structured reasoning for consensus decisions 

### Orchestration Process

The diagnostic workflow follows a structured multi-round process where each round consists of:

```
Initial Case → Panel Deliberation
                      ↓
    [Dr. Hypothesis, Dr. Test-Chooser, Dr. Challenger, 
     Dr. Stewardship, Dr. Checklist contribute in parallel]
                      ↓
    Consensus Coordinator synthesizes all inputs → ONE action chosen:
    [ASK_QUESTIONS | ORDER_TESTS | MAKE_DIAGNOSIS]
                      ↓
           Action executed → Findings updated → Next Round
                      ↓
        (Repeat until diagnosis made or max_rounds reached)
```

**Key Workflow Details:**
- Each round begins with all 5 specialist agents contributing analyses
- Consensus Coordinator synthesizes all agent inputs into a single decision
- Exactly one action type is chosen per round: questions, tests, or diagnosis
- **Final Round Forcing Logic**: When `max_rounds` is reached, Consensus Coordinator must make diagnosis
  - Automatically selects most probable diagnosis from Dr. Hypothesis if available
  - Forces diagnosis even if confidence is below normal threshold (≥85%)
  - Provides fallback diagnosis if no hypotheses are available
  - Ensures every diagnostic case reaches a conclusion
- Budget constraints can terminate early with forced diagnosis

## 📁 File Structure

```
src/
├── diagnostic_orchestrator.py          # Main orchestrator and agent implementations
├── cost_estimator.py                   # Healthcare cost estimation and budgeting
├── test_run_diagnostic_orchestrator.py # Demonstration and testing script
└── main.py                             # FastAPI integration
```

## 🚀 API Endpoints

### 1. Execute Diagnostic Case
```http
POST /api/diagnostic/case
Content-Type: application/json

{
    "case_info": "Patient presentation text...",
    "max_rounds": 10,
    "budget_limit": 5000.0,
    "execution_mode": "unconstrained"
}
```

**Execution Modes:**
- `instant` - Diagnosis based solely on initial presentation (bypasses multi-round process)
- `questions_only` - Can ask questions but no diagnostic tests allowed
- `unconstrained` - Full diagnostic workup with all actions available (default mode)

**Budget Control:**
- Use `budget_limit` parameter (not execution_mode) to enforce cost constraints
- When budget is reached, system automatically forces diagnosis with best available hypothesis


### 2. Get Case Summary
```http
GET /api/diagnostic/case/{case_id}/summary
```

Returns:
```json
{
    "case_id": "uuid",
    "final_diagnosis": "Diagnosis text",
    "confidence_score": 0.85,
    "total_cost": 2450.00,
    "rounds_completed": 3,
    "trace_count": 15
}
```

### 3. Get Execution Traces
```http
GET /api/diagnostic/case/{case_id}/traces
```

Returns detailed step-by-step execution logs with timestamps, actors, and decision rationales.

### 4. Get Agent Messages
```http
GET /api/diagnostic/case/{case_id}/agent-messages
```

Returns inter-agent communications during the chain-of-debate process.

## 💰 Cost Management

The system implements basic healthcare cost estimation. The following are some mock data for tests and test costs:

### Test Categories and Pricing
- **Basic Labs**: $25-$150 (CBC, CMP, TSH, etc.)
- **Imaging**: $200-$1,600 (X-ray, CT, MRI, Ultrasound)
- **Procedures**: $500-$3,000 (Biopsy, Endoscopy, Catheterization)
- **Physician Visits**: $300 per visit

## 🔧 Configuration

### Environment Variables
```bash
# Required for Azure OpenAI integration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=your-model-deployment

# Optional: Enable development mode (bypasses auth)
DEVELOPMENT_MODE=true
```

## 📝 Usage Examples

### Basic Case Execution
```python
from diagnostic_orchestrator import DiagnosticOrchestrator

orchestrator = DiagnosticOrchestrator()

case_info = """
A 45-year-old male presents with acute chest pain, 
radiating to left arm. History of hypertension and smoking.
Vital signs: BP 150/90, HR 110, RR 20.
"""

session = await orchestrator.run_diagnostic_case(
    case_info=case_info,
    execution_mode="unconstrained"
)

print(f"Diagnosis: {session.final_diagnosis}")
print(f"Confidence: {session.confidence_score:.1%}")
print(f"Total Cost: ${session.total_cost:.2f}")
```

### Budget-Constrained Execution
```python
session = await orchestrator.run_diagnostic_case(
    case_info=case_info,
    budget_limit=1000.0,
    execution_mode="unconstrained"  # Uses budget_limit for constraint
)
```

### Trace Analysis
```python
traces = orchestrator.get_session_traces(session.case_id)

for trace in traces:
    print(f"[{trace.timestamp}] {trace.actor}: {trace.content}")
    if trace.cost_impact:
        print(f"  Cost Impact: ${trace.cost_impact:.2f}")
```

## 🧪 Testing and Demonstration

Run the demo/test script to try the orchestrator in action:

```bash
cd src
python test_run_diagnostic_orchestrator.py
```

This will show:
- Multi-agent coordination examples
- Cost estimation capabilities  
- Different execution modes
- Trace generation and analysis

## 🔐 Security and Compliance

- Basic implementation for proof-of-concept and demo purposes

## 📚 References

- Microsoft AI Research: "Sequential Diagnosis with Language Models" (2025)