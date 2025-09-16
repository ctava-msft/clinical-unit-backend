"""
MAI Diagnostic Orchestrator Demo Script

This script demonstrates the functionality of the MAI-DxO diagnostic orchestrator
with sample clinical cases. It shows:
- Multi-agent coordination and chain-of-debate process
- Cost-aware diagnostic planning
- Step-by-step execution traces
- Different execution modes (instant, questions-only, budgeted, unconstrained)

Run this script to see the orchestrator in action with mock data when
Azure OpenAI is not available.
"""

import asyncio
import json
from datetime import datetime
from diagnostic_orchestrator import DiagnosticOrchestrator, CaseExecutionSession
from cost_estimator import cost_estimator

# Sample clinical cases for demonstration
SAMPLE_CASES = [
    {
        "id": "case_001",
        "title": "Chest Pain in Emergency Department",
        "case_info": """A 45-year-old male presents to the emergency department with acute onset chest pain that started 2 hours ago. The pain is described as crushing, substernal, and radiates to the left arm. He has a history of hypertension and smoking. Vital signs show BP 150/90, HR 110, RR 20, O2 sat 96% on room air."""
    },
    {
        "id": "case_002", 
        "title": "Fever and Altered Mental Status",
        "case_info": """A 72-year-old woman is brought to the hospital by her daughter for confusion and fever over the past 3 days. She has been increasingly disoriented and has difficulty recognizing family members. Temperature is 38.8°C (101.8°F), BP 100/60, HR 105. She has a history of diabetes and recent UTI treatment."""
    },
    {
        "id": "case_003",
        "title": "Shortness of Breath in Young Adult", 
        "case_info": """A 28-year-old female presents with acute onset shortness of breath and pleuritic chest pain that began suddenly while watching TV. She recently returned from a 10-hour flight from Europe 3 days ago. She is on oral contraceptives. Vital signs: BP 110/70, HR 120, RR 24, O2 sat 91% on room air."""
    }
]

class MockDiagnosticOrchestrator:
    """Mock orchestrator for demonstration when Azure OpenAI is not available"""
    
    def __init__(self):
        self.active_sessions = {}
    
    async def run_diagnostic_case(self, case_info: str, max_rounds: int = 10,
                                 budget_limit: float = None, 
                                 execution_mode: str = "unconstrained") -> CaseExecutionSession:
        """Mock implementation of diagnostic case execution"""
        import uuid
        
        case_id = str(uuid.uuid4())
        session = CaseExecutionSession(case_id, case_info)
        self.active_sessions[case_id] = session
        
        # Simulate the orchestration process with mock data
        session.add_trace(
            "internal_debate",
            "System", 
            f"Mock orchestration started for case {case_id[:8]}...",
            {"execution_mode": execution_mode, "budget_limit": budget_limit}
        )
        
        # Mock round 1 - Initial assessment
        session.increment_round()
        session.add_trace("internal_debate", "System", "=== DIAGNOSTIC ROUND 1 ===")
        
        # Mock agent contributions
        session.add_agent_message("Dr. Hypothesis", "hypothesis_update", 
            "Initial differential diagnosis: 1. Acute coronary syndrome (0.7), 2. Pulmonary embolism (0.2), 3. Aortic dissection (0.1)")
        
        session.add_agent_message("Dr. Test-Chooser", "test_recommendation",
            "Recommended tests: 1. EKG (high priority), 2. Troponin (high priority), 3. Chest X-ray (moderate priority)")
        
        session.add_agent_message("Dr. Challenger", "challenge", 
            "Consider: Are we anchoring on cardiac causes? What about pneumothorax or musculoskeletal pain?")
        
        session.add_agent_message("Dr. Stewardship", "stewardship_review",
            "EKG and troponin are cost-effective first steps. Hold off on CT angiogram until basic workup complete.")
        
        session.add_agent_message("Dr. Checklist", "quality_control",
            "Validation: All recommended tests are appropriate and orderable. Good systematic approach.")
        
        # Mock test ordering and costs
        mock_tests = ["EKG", "Troponin", "Chest X-ray"]
        total_cost = 0
        for test in mock_tests:
            test_cost = cost_estimator.estimate_test_cost(test)
            total_cost += test_cost.total_cost
            session.add_trace("order_tests", "Panel Consensus", f"Ordered: {test}", 
                            {"test_cost": test_cost.total_cost}, test_cost.total_cost)
        
        # Mock round 2 - Results interpretation  
        session.increment_round()
        session.add_trace("internal_debate", "System", "=== DIAGNOSTIC ROUND 2 ===")
        
        # Mock test results
        session.add_trace("ask_questions", "Gatekeeper", 
            "EKG: ST elevation in leads II, III, aVF. Troponin: 15.2 ng/mL (elevated). Chest X-ray: Normal cardiac silhouette, clear lungs")
        
        # Updated hypothesis
        session.add_agent_message("Dr. Hypothesis", "hypothesis_update",
            "Updated diagnosis based on results: 1. ST-elevation MI (inferior) (0.95), 2. NSTEMI (0.04), 3. Other (0.01)")
        
        # Final diagnosis
        session.final_diagnosis = "ST-elevation myocardial infarction (inferior wall)"
        session.confidence_score = 0.95
        
        session.add_trace("make_diagnosis", "Panel Consensus", 
            f"Final Diagnosis: {session.final_diagnosis}",
            {"confidence": session.confidence_score})
        
        session.add_trace("cost_estimation", "System", 
            f"Total case cost: ${session.total_cost:.2f}")
        
        return session
    
    def get_session_traces(self, case_id: str):
        """Get traces for a session"""
        if case_id in self.active_sessions:
            return self.active_sessions[case_id].traces
        return []
    
    def get_session_summary(self, case_id: str):
        """Get session summary"""
        if case_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[case_id]
        return {
            "case_id": case_id,
            "session_id": session.session_id,
            "final_diagnosis": session.final_diagnosis,
            "confidence_score": session.confidence_score,
            "total_cost": session.total_cost,
            "rounds_completed": session.current_round,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "trace_count": len(session.traces),
            "agent_message_count": len(session.agent_messages)
        }

async def demonstrate_orchestrator():
    """Demonstrate the diagnostic orchestrator with sample cases"""
    
    print("🔬 MAI Diagnostic Orchestrator Demonstration")
    print("=" * 60)
    
    # Try to create real orchestrator, fall back to mock
    try:
        orchestrator = DiagnosticOrchestrator()
        print("✓ Using real DiagnosticOrchestrator with Azure OpenAI")
    except Exception as e:
        print(f"⚠ Azure OpenAI not available ({e})")
        print("✓ Using MockDiagnosticOrchestrator for demonstration")
        orchestrator = MockDiagnosticOrchestrator()
    
    # Demonstrate different execution modes
    execution_modes = ["instant", "questions_only", "unconstrained"]
    
    for i, case in enumerate(SAMPLE_CASES[:1]):  # Just run first case for demo
        print(f"\n📋 Case {i+1}: {case['title']}")
        print("-" * 40)
        print(f"Initial presentation: {case['case_info'][:100]}...")
        
        for mode in execution_modes:
            print(f"\n🔧 Execution Mode: {mode.upper()}")
            print("-" * 20)
            
            try:
                # Run diagnostic case
                session = await orchestrator.run_diagnostic_case(
                    case_info=case['case_info'],
                    max_rounds=3,
                    budget_limit=5000.0 if mode == "budgeted" else None,
                    execution_mode=mode
                )
                
                # Display summary
                summary = orchestrator.get_session_summary(session.case_id)
                if summary:
                    print(f"📊 Results:")
                    print(f"   Final Diagnosis: {summary.get('final_diagnosis', 'None')}")
                    print(f"   Confidence: {summary.get('confidence_score', 0):.1%}")
                    print(f"   Total Cost: ${summary.get('total_cost', 0):.2f}")
                    print(f"   Rounds: {summary.get('rounds_completed', 0)}")
                
                # Show key traces
                traces = orchestrator.get_session_traces(session.case_id)
                if traces:
                    print(f"\n📝 Key Execution Traces (showing first 3):")
                    for trace in traces[:3]:
                        timestamp = trace.timestamp.strftime("%H:%M:%S") if hasattr(trace, 'timestamp') else "00:00:00"
                        actor = getattr(trace, 'actor', 'Unknown')
                        content = getattr(trace, 'content', str(trace))[:80]
                        print(f"   [{timestamp}] {actor}: {content}...")
                
            except Exception as e:
                print(f"❌ Error running case in {mode} mode: {e}")
    
    print(f"\n💰 Cost Estimation Examples:")
    print("-" * 30)
    
    # Demonstrate cost estimation
    sample_tests = ["EKG", "CT Chest with Contrast", "MRI Brain", "CBC", "Troponin"]
    
    for test in sample_tests:
        cost = cost_estimator.estimate_test_cost(test)
        print(f"   {test:<25} ${cost.total_cost:>7.2f} ({cost.cost_category})")
    
    # Show cheaper alternatives
    expensive_test = "CT Chest with Contrast"
    alternatives = cost_estimator.suggest_cheaper_alternatives(expensive_test)
    if alternatives:
        print(f"\n💡 Cheaper alternatives for {expensive_test}:")
        for alt in alternatives[:2]:  # Show first 2 alternatives
            print(f"   → {alt['alternative']} (saves ${alt['cost_savings']:.2f})")
            print(f"     Rationale: {alt['rationale']}")
    
    print(f"\n✅ Demonstration completed!")

def demonstrate_cost_estimator():
    """Demonstrate the cost estimation capabilities"""
    print("\n💰 Cost Estimator Demonstration")
    print("=" * 40)
    
    # Test various diagnostic procedures
    test_categories = {
        "Basic Labs": ["CBC", "CMP", "Urinalysis", "TSH"],
        "Cardiac Tests": ["EKG", "Troponin", "Echocardiogram", "Stress Test"],
        "Imaging": ["Chest X-ray", "CT Chest", "MRI Brain", "Ultrasound Abdomen"],
        "Procedures": ["Colonoscopy", "Biopsy", "Lumbar Puncture"]
    }
    
    for category, tests in test_categories.items():
        print(f"\n{category}:")
        total_category_cost = 0
        for test in tests:
            cost = cost_estimator.estimate_test_cost(test)
            print(f"  {test:<20} ${cost.total_cost:>7.2f} ({cost.cost_category})")
            total_category_cost += cost.total_cost
        print(f"  {'TOTAL:':<20} ${total_category_cost:>7.2f}")

if __name__ == "__main__":
    print("🚀 Starting MAI Diagnostic Orchestrator Demo")
    
    # Run cost estimator demo first (synchronous)
    demonstrate_cost_estimator()
    
    # Run main orchestrator demo (async)
    asyncio.run(demonstrate_orchestrator())
    
    print("\n🎯 Demo completed! The orchestrator is ready for integration into the clinical unit backend.")
    print("\nAPI Endpoints available:")
    print("  POST /api/diagnostic/case - Run diagnostic orchestration")
    print("  GET  /api/diagnostic/case/{case_id}/summary - Get case summary")
    print("  GET  /api/diagnostic/case/{case_id}/traces - Get execution traces")
    print("  GET  /api/diagnostic/case/{case_id}/agent-messages - Get agent messages")