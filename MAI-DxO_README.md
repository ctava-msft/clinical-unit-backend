# MAI Diagnostic Orchestrator (MAI-DxO) Implementation

This implementation brings the MAI Diagnostic Orchestrator pattern from Microsoft AI's research paper to the Clinical Unit Backend. The system provides AI-powered diagnostic reasoning through multi-agent coordination, following evidence-based medicine principles with cost-conscious decision making.

## 🎯 Overview

The MAI-DxO system simulates a panel of specialist physicians working collaboratively to solve diagnostic cases, implementing the methodology described in "Sequential Diagnosis with Language Models" (Microsoft AI, 2025).

### Key Features

- **Multi-Agent Orchestration**: Five specialized diagnostic agents with distinct roles
- **Chain-of-Debate Process**: Structured deliberation between agents for consensus building
- **Cost-Aware Planning**: Budget tracking and cost-effectiveness analysis
- **Comprehensive Tracing**: Step-by-step execution logs with actor-labeled decision trails
- **Multiple Execution Modes**: From instant diagnosis to full sequential reasoning
- **Azure AI Integration**: Built for Azure OpenAI and AI Foundry services

## 🏗️ Architecture

### Specialized Diagnostic Agents

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

### Orchestration Process

```
Initial Case → Agent Contributions → Chain of Debate → Consensus → Action
                      ↓
         [Hypothesis, Tests, Challenges, Stewardship, QC]
                      ↓
              Cost Analysis → Budget Check → Execute → Update → Repeat
```

## 📁 File Structure

```
src/
├── diagnostic_orchestrator.py    # Main orchestrator and agent implementations
├── cost_estimator.py            # Healthcare cost estimation and budgeting
├── demo_orchestrator.py         # Demonstration and testing script
└── main.py                      # FastAPI integration (updated)
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
- `instant` - Diagnosis based solely on initial presentation
- `questions_only` - Can ask questions but no diagnostic tests
- `budgeted` - Full reasoning with budget constraints
- `unconstrained` - Full diagnostic workup without cost limits
- `ensemble` - Multiple parallel reasoning chains with consensus

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

The system implements sophisticated healthcare cost estimation:

### Test Categories and Pricing
- **Basic Labs**: $25-$150 (CBC, CMP, TSH, etc.)
- **Imaging**: $200-$1,600 (X-ray, CT, MRI, Ultrasound)
- **Procedures**: $500-$3,000 (Biopsy, Endoscopy, Catheterization)
- **Physician Visits**: $300 per visit

### Cost-Effectiveness Features
- Real-time budget tracking during case execution
- Cheaper alternative suggestions
- Cost category classification (low/moderate/high/very high)
- Budget limit enforcement with graceful degradation

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

### Azure AI Foundry Integration
The orchestrator is designed to work with Azure AI Foundry services and follows Semantic Kernel patterns for:
- Model deployment and scaling
- Cost monitoring and optimization  
- Performance analytics and monitoring
- Enterprise security and compliance

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
    execution_mode="budgeted"
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

Run the demonstration script to see the orchestrator in action:

```bash
cd src
python demo_orchestrator.py
```

This will show:
- Multi-agent coordination examples
- Cost estimation capabilities  
- Different execution modes
- Trace generation and analysis

## 🔬 Research Alignment

This implementation closely follows the MAI-DxO research methodology:

### Paper Implementation Fidelity
- ✅ **Five-Agent Panel**: All specialist roles implemented
- ✅ **Chain of Debate**: Structured inter-agent deliberation
- ✅ **Cost Integration**: Budget tracking and stewardship
- ✅ **Execution Modes**: Multiple reasoning strategies
- ✅ **Trace Generation**: Comprehensive decision logging
- ✅ **Bayesian Updates**: Hypothesis probability refinement

### Enhancements Beyond Paper
- 🔥 **Azure AI Integration**: Enterprise-grade deployment
- 🔥 **FastAPI Endpoints**: REST API for clinical integration
- 🔥 **Real-time Cost Tracking**: Live budget monitoring
- 🔥 **Comprehensive Tracing**: Enhanced observability
- 🔥 **Flexible Configuration**: Multiple deployment modes

## 🛠️ Development and Extension

### Adding New Agents
Extend `BaseSpecializedAgent` and implement the `contribute()` method:

```python
class DrSpecialist(BaseSpecializedAgent):
    async def contribute(self, case_info, findings, hypotheses, session):
        # Custom reasoning logic
        return {"specialist_insight": "..."}
```

### Custom Cost Models
Extend `CostEstimator` for organization-specific pricing:

```python
class CustomCostEstimator(CostEstimator):
    def __init__(self):
        super().__init__()
        # Load custom pricing data
        self.load_institutional_pricing()
```

### Integration Points
- **EHR Systems**: Connect to electronic health records
- **PACS Integration**: Interface with imaging systems  
- **Lab Systems**: Real-time laboratory result integration
- **Clinical Decision Support**: Embed in existing workflows

## 📊 Performance Characteristics

Based on MAI-DxO research findings:

- **Diagnostic Accuracy**: Up to 85.5% on challenging cases
- **Cost Reduction**: 20-70% vs. unstructured approaches
- **Processing Time**: 2-5 minutes per case (model-dependent)
- **Scalability**: Supports concurrent case processing

## 🔐 Security and Compliance

- Authentication integration (production/development modes)
- Audit trail generation for all diagnostic decisions
- HIPAA-compliant data handling patterns
- Role-based access control for sensitive operations

## 📈 Future Enhancements

- **Ensemble Orchestration**: Multiple parallel reasoning chains
- **Learning Integration**: Feedback loops for continuous improvement
- **Specialty Modules**: Domain-specific diagnostic expertise
- **Real-world Validation**: Integration with clinical outcome data
- **Advanced Analytics**: Performance monitoring and optimization

## 📚 References

- Microsoft AI Research: "Sequential Diagnosis with Language Models" (2025)
- Clinical Decision Making: Evidence-based medicine principles
- Healthcare Economics: Cost-effectiveness analysis frameworks
- Multi-Agent Systems: Collaborative AI architectures

---

*This implementation transforms cutting-edge AI research into production-ready clinical decision support tools, bringing the power of multi-agent diagnostic reasoning to real-world healthcare settings.*