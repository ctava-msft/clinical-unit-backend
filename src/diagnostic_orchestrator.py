"""
Diagnostic Orchestrator

Implementation of the diagnostic orchestrator pattern from the Microsoft AI research paper,
featuring multi-agent coordination for clinical diagnosis with role-specialized reasoning agents.

This module provides:
- Multi-agent orchestration framework with 5 specialized medical roles
- Chain of debate coordination between agents
- Comprehensive execution tracing and decision logging
- Cost-aware diagnostic planning
"""

import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from pydantic import BaseModel
import openai
from openai import AsyncOpenAI
# from dotenv import load_dotenv

# Load environment variables
# load_dotenv()

# Import cost estimation capabilities
from cost_estimator import cost_estimator, TestCost

# Trace and execution models
class ActionType(str, Enum):
    """Types of actions the diagnostic panel can take after deliberation"""
    ASK_QUESTIONS = "ask_questions"
    ORDER_TESTS = "order_tests" 
    MAKE_DIAGNOSIS = "make_diagnosis"

@dataclass
class DiagnosticHypothesis:
    """Represents a diagnostic hypothesis with probability"""
    condition: str
    probability: float
    reasoning: str
    supporting_evidence: List[str] = field(default_factory=list)
    contradictory_evidence: List[str] = field(default_factory=list)

@dataclass
class TestRecommendation:
    """Represents a recommended diagnostic test"""
    test_name: str
    rationale: str
    estimated_cost: Optional[float] = None
    priority: int = 1  # 1=highest, 3=lowest
    discriminative_value: str = ""
    
@dataclass
class AgentMessage:
    """Represents a message from one of the specialized agents"""
    agent_role: str
    timestamp: datetime
    message_type: str  # "hypothesis", "test_recommendation", "challenge", "stewardship_review"
    content: str
    structured_data: Optional[Dict[str, Any]] = None

@dataclass
class ExecutionTrace:
    """Comprehensive trace of the diagnostic orchestration execution"""
    case_id: str
    session_id: str
    timestamp: datetime
    round_number: int
    action_type: ActionType
    actor: str
    content: str
    structured_data: Optional[Dict[str, Any]] = None
    cost_impact: Optional[float] = None

class CaseExecutionSession:
    """Manages a single diagnostic case execution session"""
    
    def __init__(self, case_id: str, initial_case_info: str):
        self.case_id = case_id
        self.session_id = str(uuid.uuid4())
        self.initial_case_info = initial_case_info
        self.traces: List[ExecutionTrace] = []
        self.agent_messages: List[AgentMessage] = []
        self.current_round = 0
        self.total_cost = 0.0
        self.final_diagnosis: Optional[str] = None
        self.confidence_score: Optional[float] = None
        self.created_at = datetime.now()
        
    def add_trace(self, action_type: ActionType, actor: str, content: str, 
                  structured_data: Optional[Dict[str, Any]] = None, 
                  cost_impact: Optional[float] = None):
        """Add an execution trace entry"""
        trace = ExecutionTrace(
            case_id=self.case_id,
            session_id=self.session_id,
            timestamp=datetime.now(),
            round_number=self.current_round,
            action_type=action_type,
            actor=actor,
            content=content,
            structured_data=structured_data,
            cost_impact=cost_impact
        )
        self.traces.append(trace)
        
        if cost_impact:
            self.total_cost += cost_impact
            
    def add_agent_message(self, agent_role: str, message_type: str, content: str,
                         structured_data: Optional[Dict[str, Any]] = None):
        """Add a message from one of the specialized agents"""
        message = AgentMessage(
            agent_role=agent_role,
            timestamp=datetime.now(),
            message_type=message_type,
            content=content,
            structured_data=structured_data
        )
        self.agent_messages.append(message)
        
    def increment_round(self):
        """Move to the next diagnostic round"""
        self.current_round += 1

class BaseSpecializedAgent:
    """Base class for all specialized diagnostic agents"""
    
    def __init__(self, role_name: str, client: AsyncOpenAI):
        self.role_name = role_name
        self.client = client
        self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        
    async def _call_llm(self, system_prompt: str, user_message: str, 
                       temperature: float = 0.7) -> str:
        """Make an async call to the language model"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error in LLM call: {str(e)}"
    
    async def contribute(self, case_info: str, previous_findings: List[str], 
                        current_hypotheses: List[DiagnosticHypothesis],
                        session: CaseExecutionSession) -> Dict[str, Any]:
        """Override this method in specialized agents"""
        raise NotImplementedError("Subclasses must implement contribute method")

class DrHypothesis(BaseSpecializedAgent):
    """
    Dr. Hypothesis - Maintains probability-ranked differential diagnosis
    Updates probabilities in a Bayesian manner after each new finding
    """
    
    def __init__(self, client: AsyncOpenAI):
        super().__init__("Dr. Hypothesis", client)
        
    async def contribute(self, case_info: str, previous_findings: List[str], 
                        current_hypotheses: List[DiagnosticHypothesis],
                        session: CaseExecutionSession) -> Dict[str, Any]:
        
        system_prompt = """You are Dr. Hypothesis, a specialist in differential diagnosis and Bayesian reasoning.
        
Your role:
1. Maintain a probability-ranked differential diagnosis with the top 3 most likely conditions
2. Update probabilities based on new findings using Bayesian reasoning
3. Provide clear reasoning for probability updates
4. Consider both common and rare conditions based on clinical presentation

Format your response as JSON with:
{
    "hypotheses": [
        {
            "condition": "condition name",
            "probability": 0.XX,
            "reasoning": "detailed reasoning",
            "supporting_evidence": ["evidence1", "evidence2"],
            "contradictory_evidence": ["contradiction1"]
        }
    ],
    "bayesian_updates": "explanation of how probabilities changed",
    "confidence_level": "low/medium/high"
}"""

        findings_text = "\n".join(previous_findings) if previous_findings else "No additional findings yet."
        current_hyp_text = "\n".join([f"- {h.condition} ({h.probability:.2f}): {h.reasoning}" 
                                     for h in current_hypotheses]) if current_hypotheses else "No current hypotheses."
        
        user_message = f"""
Initial Case: {case_info}

Previous Findings:
{findings_text}

Current Hypotheses:
{current_hyp_text}

Please provide updated differential diagnosis with probability estimates.
"""

        response = await self._call_llm(system_prompt, user_message)
        session.add_agent_message(self.role_name, "hypothesis_update", response)
        
        try:
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return parsed
        except:
            pass
            
        # Fallback if JSON parsing fails
        return {
            "hypotheses": [],
            "bayesian_updates": response,
            "confidence_level": "low"
        }

class DrTestChooser(BaseSpecializedAgent):
    """
    Dr. Test-Chooser - Selects diagnostic tests that maximally discriminate 
    between leading hypotheses
    """
    
    def __init__(self, client: AsyncOpenAI):
        super().__init__("Dr. Test-Chooser", client)
        
    async def contribute(self, case_info: str, previous_findings: List[str], 
                        current_hypotheses: List[DiagnosticHypothesis],
                        session: CaseExecutionSession) -> Dict[str, Any]:
        
        system_prompt = """You are Dr. Test-Chooser, a specialist in diagnostic test selection and evidence-based medicine.

Your role:
1. Select up to 3 diagnostic tests per round that maximally discriminate between leading hypotheses
2. Prioritize tests with highest diagnostic yield
3. Consider test characteristics: sensitivity, specificity, cost-effectiveness
4. Avoid redundant or low-yield investigations

Format your response as JSON:
{
    "recommended_tests": [
        {
            "test_name": "specific test name",
            "rationale": "why this test discriminates between hypotheses",
            "priority": 1-3,
            "discriminative_value": "which conditions this test helps distinguish",
            "estimated_cost": estimated_cost_in_dollars
        }
    ],
    "reasoning": "overall test selection strategy"
}"""

        hypotheses_text = "\n".join([f"- {h.condition} ({h.probability:.2f})" 
                                   for h in current_hypotheses[:3]]) if current_hypotheses else "No hypotheses available."
        findings_text = "\n".join(previous_findings) if previous_findings else "No findings yet."
        
        user_message = f"""
Case: {case_info}

Current Top Hypotheses:
{hypotheses_text}

Previous Findings:
{findings_text}

Select the most discriminative diagnostic tests to differentiate between these hypotheses.
"""

        response = await self._call_llm(system_prompt, user_message)
        session.add_agent_message(self.role_name, "test_recommendation", response)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
            
        return {
            "recommended_tests": [],
            "reasoning": response
        }

class DrChallenger(BaseSpecializedAgent):
    """
    Dr. Challenger - Acts as devil's advocate, identifies anchoring bias,
    highlights contradictory evidence
    """
    
    def __init__(self, client: AsyncOpenAI):
        super().__init__("Dr. Challenger", client)
        
    async def contribute(self, case_info: str, previous_findings: List[str], 
                        current_hypotheses: List[DiagnosticHypothesis],
                        session: CaseExecutionSession) -> Dict[str, Any]:
        
        system_prompt = """You are Dr. Challenger, the devil's advocate who prevents diagnostic errors.

Your role:
1. Identify potential anchoring bias in current hypotheses
2. Highlight contradictory evidence that doesn't fit leading diagnoses
3. Propose alternative diagnoses that might be overlooked
4. Suggest tests that could falsify current leading diagnosis
5. Challenge assumptions and cognitive shortcuts

Format your response as JSON:
{
    "challenges": [
        {
            "target_hypothesis": "hypothesis being challenged",
            "challenge_type": "anchoring bias / contradictory evidence / alternative explanation",
            "reasoning": "detailed challenge reasoning",
            "alternative_hypothesis": "proposed alternative if applicable"
        }
    ],
    "falsifying_tests": ["tests that could disprove current leading diagnosis"],
    "overlooked_possibilities": ["diagnoses that might be missed"],
    "cognitive_bias_warnings": "warnings about potential reasoning errors"
}"""

        hypotheses_text = "\n".join([f"- {h.condition} ({h.probability:.2f}): {h.reasoning}" 
                                   for h in current_hypotheses[:3]]) if current_hypotheses else "No hypotheses to challenge."
        findings_text = "\n".join(previous_findings) if previous_findings else "No findings yet."
        
        user_message = f"""
Case: {case_info}

Current Leading Hypotheses:
{hypotheses_text}

Accumulated Findings:
{findings_text}

Challenge these hypotheses. What are we potentially missing or overlooking?
"""

        response = await self._call_llm(system_prompt, user_message)
        session.add_agent_message(self.role_name, "challenge", response)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
            
        return {
            "challenges": [],
            "falsifying_tests": [],
            "overlooked_possibilities": [],
            "cognitive_bias_warnings": response
        }

class DrStewardship(BaseSpecializedAgent):
    """
    Dr. Stewardship - Enforces cost-conscious care, advocates for cheaper alternatives,
    vetoes low-yield expensive tests
    """
    
    def __init__(self, client: AsyncOpenAI):
        super().__init__("Dr. Stewardship", client)
        
    async def contribute(self, case_info: str, previous_findings: List[str], 
                        current_hypotheses: List[DiagnosticHypothesis],
                        session: CaseExecutionSession,
                        proposed_tests: List[TestRecommendation] = None) -> Dict[str, Any]:
        
        system_prompt = """You are Dr. Stewardship, the guardian of cost-effective and value-based care.

Your role:
1. Review proposed tests for cost-effectiveness
2. Suggest cheaper alternatives when diagnostically equivalent
3. Veto low-yield expensive tests
4. Advocate for step-wise diagnostic approach
5. Balance diagnostic yield against cost and patient burden

Format your response as JSON:
{
    "cost_analysis": [
        {
            "test_name": "test being reviewed",
            "approval_status": "approved / conditional / rejected",
            "reasoning": "cost-benefit analysis",
            "cheaper_alternative": "alternative test if applicable",
            "cost_category": "low / moderate / high / very high"
        }
    ],
    "budget_recommendation": "continue / proceed with caution / stop and reassess",
    "stewardship_notes": "overall cost-consciousness guidance"
}"""

        proposed_tests_text = ""
        if proposed_tests:
            proposed_tests_text = "\n".join([f"- {t.test_name}: {t.rationale} (Est. cost: ${t.estimated_cost or 'unknown'})" 
                                           for t in proposed_tests])
        
        current_cost = session.total_cost
        
        hypotheses_summary = "\n".join([f"- {h.condition} ({h.probability:.2f})" for h in current_hypotheses[:3]]) if current_hypotheses else "No hypotheses yet."
        
        user_message = f"""
Case: {case_info}

Current Cumulative Cost: ${current_cost:.2f}

Proposed Tests:
{proposed_tests_text or "No tests proposed yet."}

Current Hypotheses:
{hypotheses_summary}

Review these tests from a cost-effectiveness perspective. Are there cheaper alternatives?
"""

        response = await self._call_llm(system_prompt, user_message)
        session.add_agent_message(self.role_name, "stewardship_review", response)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
            
        return {
            "cost_analysis": [],
            "budget_recommendation": "continue",
            "stewardship_notes": response
        }

class DrChecklist(BaseSpecializedAgent):
    """
    Dr. Checklist - Performs quality control, ensures valid test names,
    maintains internal consistency
    """
    
    def __init__(self, client: AsyncOpenAI):
        super().__init__("Dr. Checklist", client)
        
    async def contribute(self, case_info: str, previous_findings: List[str], 
                        current_hypotheses: List[DiagnosticHypothesis],
                        session: CaseExecutionSession) -> Dict[str, Any]:
        
        system_prompt = """You are Dr. Checklist, the quality control specialist ensuring systematic and thorough care.

Your role:
1. Assess completeness of current diagnostic workup
2. Identify missing critical information or assessments
3. Evaluate systematic approach to diagnosis
4. Flag any logical inconsistencies or gaps in reasoning
5. Provide quality assessment of current diagnostic process

Format your response as JSON:
{
    "missing_info": ["list of missing critical information"],
    "systematic_gaps": ["gaps in systematic approach"],
    "quality_concerns": ["any quality issues identified"],
    "recommended_next_steps": ["suggested next diagnostic steps"],
    "completeness_assessment": "overall assessment of diagnostic completeness",
    "quality_score": 1-10
}"""

        hypotheses_summary = "\n".join([f"- {h.condition} ({h.probability:.2f}): {h.reasoning}" for h in current_hypotheses]) if current_hypotheses else "No hypotheses available."
        findings_text = "\n".join(previous_findings) if previous_findings else "No additional findings yet."
        
        user_message = f"""
Case: {case_info}

Current Hypotheses:
{hypotheses_summary}

Accumulated Findings:
{findings_text}

Current Round: {session.current_round}
Total Cost So Far: ${session.total_cost:.2f}

Perform quality control assessment of the current diagnostic approach and identify any gaps or concerns.
"""

        response = await self._call_llm(system_prompt, user_message)
        session.add_agent_message(self.role_name, "quality_control", response)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
            
        return {
            "missing_info": [],
            "systematic_gaps": [],
            "quality_concerns": [],
            "recommended_next_steps": [],
            "completeness_assessment": response,
            "quality_score": 5
        }

class ConsensusCoordinator(BaseSpecializedAgent):
    """
    Consensus Coordinator - Synthesizes all panel recommendations into a single consensus decision
    """
    
    def __init__(self, client: AsyncOpenAI):
        super().__init__("Consensus Coordinator", client)
        
    async def synthesize_consensus(self, case_info: str, previous_findings: List[str],
                                 session: CaseExecutionSession,
                                 panel_contributions: Dict[str, Any], 
                                 max_rounds: int = 10) -> Dict[str, Any]:
        
        # Check if this is the final round
        is_final_round = session.current_round >= max_rounds
        
        system_prompt = f"""You are the Consensus Coordinator, responsible for synthesizing the diagnostic panel's recommendations into a single consensus decision.

Your role:
1. Review all panel member contributions (Dr. Hypothesis, Dr. Test-Chooser, Dr. Challenger, Dr. Stewardship, Dr. Checklist)
2. Weigh the evidence and recommendations from each specialist
3. Make a consensus decision on the next action to take
4. Provide clear reasoning for the chosen action

You must choose exactly ONE of these three actions:
- ask_questions: When more clinical information is needed
- order_tests: When diagnostic tests will help differentiate hypotheses
- make_diagnosis: When confidence is sufficient for diagnosis

Decision Guidelines:
- Make Diagnosis: When diagnostic confidence is sufficiently high (≥85%)
- Order Tests: When tests can meaningfully differentiate between top hypotheses
- Ask Questions: When additional clinical information could be of high value to clarify or refine hypotheses

CRITICAL: {"This is the FINAL ROUND. You MUST make a diagnosis based on the best available information, regardless of confidence level. Provide the most likely diagnosis with clear reasoning about the diagnostic process and available evidence." if is_final_round else ""}

Format your response as JSON:
{{
    "consensus_action": "ask_questions | order_tests | make_diagnosis",
    "action_content": {{
        "questions": ["question1", "question2"] OR
        "tests": ["test1", "test2"] OR 
        "diagnosis": "final diagnosis",
        "confidence": 0.XX
    }},
    "reasoning": "detailed explanation of why this action was chosen{"; If this is the FINAL ROUND and the diagnosis decision is made because of it, make that clear." if is_final_round else ""}",
    "panel_synthesis": "how you weighed different panel member inputs",
    "confidence_assessment": "assessment of current diagnostic confidence"
}}"""

        # Extract key information from panel contributions
        hypothesis_data = panel_contributions.get("hypothesis", {})
        test_data = panel_contributions.get("tests", {})
        challenge_data = panel_contributions.get("challenges", {})
        stewardship_data = panel_contributions.get("stewardship", {})
        checklist_data = panel_contributions.get("checklist", {})
        
        # Format panel contributions for the LLM
        panel_summary = f"""
=== Dr. Hypothesis Assessment ===
{json.dumps(hypothesis_data, indent=2)}

=== Dr. Test-Chooser Recommendations ===
{json.dumps(test_data, indent=2)}

=== Dr. Challenger Analysis ===
{json.dumps(challenge_data, indent=2)}

=== Dr. Stewardship Review ===
{json.dumps(stewardship_data, indent=2)}

=== Dr. Checklist Quality Control ===
{json.dumps(checklist_data, indent=2)}
"""

        findings_text = "\n".join(previous_findings) if previous_findings else "No additional findings yet."
        
        user_message = f"""
Case: {case_info}

Accumulated Findings:
{findings_text}

Current Round: {session.current_round} of {max_rounds} {"(FINAL ROUND - MUST DIAGNOSE)" if is_final_round else ""}
Total Cost So Far: ${session.total_cost:.2f}

Panel Member Contributions:
{panel_summary}

Based on all panel member inputs, determine the consensus action for this round. Consider:
1. Diagnostic confidence from Dr. Hypothesis
2. Available tests from Dr. Test-Chooser  
3. Concerns raised by Dr. Challenger
4. Cost considerations from Dr. Stewardship
5. Quality assessment from Dr. Checklist

{"FINAL ROUND REQUIREMENT: You must provide a diagnosis based on the best available evidence, even if confidence is lower than ideal. Select the most probable diagnosis from Dr. Hypothesis's assessment and provide clear reasoning about the diagnostic reasoning process." if is_final_round else "Choose the most appropriate action and provide detailed reasoning."}
"""

        response = await self._call_llm(system_prompt, user_message)
        session.add_agent_message(self.role_name, "consensus_decision", response)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Force diagnosis on final round if not already chosen
                if is_final_round and result.get("consensus_action") != "make_diagnosis":
                    # Extract the most likely diagnosis from panel contributions
                    hypotheses = panel_contributions.get("hypothesis", {}).get("hypotheses", [])
                    if hypotheses:
                        best_hypothesis = hypotheses[0]
                        diagnosis = best_hypothesis.get("condition", "Unknown diagnosis")
                        confidence = best_hypothesis.get("probability", 0.5)
                    else:
                        diagnosis = "Unable to determine specific diagnosis based on available information"
                        confidence = 0.3
                    
                    return {
                        "consensus_action": "make_diagnosis",
                        "action_content": {
                            "diagnosis": diagnosis,
                            "confidence": confidence
                        },
                        "reasoning": f"FINAL ROUND: Making diagnosis based on best available evidence. Original consensus action was '{result.get('consensus_action')}', but final round requires diagnosis. {result.get('reasoning', '')}",
                        "panel_synthesis": result.get("panel_synthesis", response),
                        "confidence_assessment": f"Final round forced diagnosis with confidence {confidence:.2f}"
                    }
                
                return result
        except:
            pass
            
        # Fallback response - force diagnosis on final round, ask questions otherwise
        if is_final_round:
            # Extract diagnosis from panel contributions for fallback
            hypotheses = panel_contributions.get("hypothesis", {}).get("hypotheses", [])
            if hypotheses:
                diagnosis = hypotheses[0].get("condition", "Unknown diagnosis")
                confidence = hypotheses[0].get("probability", 0.3)
            else:
                diagnosis = "Unable to determine specific diagnosis - insufficient information"
                confidence = 0.2
                
            return {
                "consensus_action": "make_diagnosis", 
                "action_content": {
                    "diagnosis": diagnosis,
                    "confidence": confidence
                },
                "reasoning": "FINAL ROUND: JSON parsing failed, but final round requires diagnosis. Making best determination from available panel inputs.",
                "panel_synthesis": f"JSON parsing error, using fallback diagnosis: {response[:200]}...",
                "confidence_assessment": f"Low confidence fallback diagnosis ({confidence:.2f}) due to parsing error"
            }
        else:
            return {
                "consensus_action": "ask_questions",
                "action_content": {
                    "questions": ["What additional clinical information would be most helpful for diagnosis?"]
                },
                "reasoning": "JSON parsing failed, defaulting to request for more information",
                "panel_synthesis": response,
                "confidence_assessment": "Unable to assess"
            }

class DiagnosticOrchestrator:
    """
    Main orchestrator that coordinates the multi-agent diagnostic process
    following the MAI-DxO pattern
    """
    
    def __init__(self, azure_openai_endpoint: str = None, azure_openai_key: str = None):
        # Initialize Azure OpenAI client
        endpoint = azure_openai_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = azure_openai_key or os.getenv("AZURE_OPENAI_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    
        # Debug output (remove after testing)
        print(f"Debug - OpenAI version: {openai.__version__}")
        print(f"Debug - Endpoint: {endpoint}")
        print(f"Debug - API Key: {'***' + api_key[-4:] if api_key else 'None'}")
        print(f"Debug - API Version: {api_version}")
        
        if not endpoint or not api_key:
            raise ValueError("Azure OpenAI endpoint and key must be provided")
            
        # Ensure endpoint has https:// prefix
        if not endpoint.startswith('https://'):
            endpoint = f"https://{endpoint}"
            
        # Use base_url approach for Azure OpenAI with standard openai library
        base_url = f"{endpoint.rstrip('/')}/openai/v1/"
        
        print(f"Debug - Constructed base_url: {base_url}")

        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            # default_headers={
            #     "api-version": api_version
            # }
        )

        print(f"Debug - Using base_url initialization: {base_url}")
        
        # Initialize specialized agents
        self.dr_hypothesis = DrHypothesis(self.client)
        self.dr_test_chooser = DrTestChooser(self.client)
        self.dr_challenger = DrChallenger(self.client)
        self.dr_stewardship = DrStewardship(self.client)
        self.dr_checklist = DrChecklist(self.client)
        self.consensus_coordinator = ConsensusCoordinator(self.client)
        
        # Execution sessions
        self.active_sessions: Dict[str, CaseExecutionSession] = {}
        
    async def run_diagnostic_case(self, case_info: str, max_rounds: int = 10,
                                 budget_limit: Optional[float] = None,
                                 execution_mode: str = "unconstrained") -> CaseExecutionSession:
        """
        Execute a complete diagnostic case using the MAI-DxO orchestration pattern
        
        Args:
            case_info: Initial case presentation text
            max_rounds: Maximum number of diagnostic rounds
            budget_limit: Optional budget constraint
            execution_mode: "instant", "questions_only", "unconstrained"
        
        Returns:
            CaseExecutionSession with complete execution trace
        """
        case_id = str(uuid.uuid4())
        session = CaseExecutionSession(case_id, case_info)
        self.active_sessions[case_id] = session
        self._current_session = session  # Store for cost tracking
        
        # Diagnostic orchestration started - no separate trace needed
        
        current_hypotheses: List[DiagnosticHypothesis] = []
        accumulated_findings: List[str] = []
        
        # Handle different execution modes
        if execution_mode == "instant":
            return await self._instant_diagnosis(session, case_info)
        elif execution_mode == "questions_only":
            return await self._questions_only_mode(session, case_info)
        
        # Main diagnostic loop - each round results in exactly one of three actions
        for round_num in range(max_rounds):
            session.increment_round()
            
            # Check budget constraints before starting round
            if budget_limit and session.total_cost >= budget_limit:
                # Force diagnosis due to budget constraints
                if current_hypotheses:
                    session.final_diagnosis = current_hypotheses[0].condition
                    session.confidence_score = current_hypotheses[0].probability
                else:
                    session.final_diagnosis = "Insufficient data - budget limit reached"
                    session.confidence_score = 0.3
                
                session.add_trace(
                    ActionType.MAKE_DIAGNOSIS,
                    "Panel Consensus", 
                    f"Final Diagnosis (Budget Limited): {session.final_diagnosis}",
                    {"confidence": session.confidence_score, "reason": "budget_limit"}
                )
                break
            
            # Execute panel deliberation - each agent contributes once
            panel_contributions = await self._execute_panel_deliberation(
                session, case_info, accumulated_findings, current_hypotheses
            )
            
            # Update current hypotheses from Dr. Hypothesis contribution
            current_hypotheses = self._parse_hypotheses_from_response(
                panel_contributions.get("hypothesis", {})
            )
                
            # Consensus Coordinator synthesizes panel input into final decision
            consensus_result = await self.consensus_coordinator.synthesize_consensus(
                case_info, accumulated_findings, session, panel_contributions, max_rounds
            )
            
            # Execute the consensus decision
            consensus_action = consensus_result.get("consensus_action")
            action_content = consensus_result.get("action_content", {})
            reasoning = consensus_result.get("reasoning", "")
            
            if consensus_action == ActionType.MAKE_DIAGNOSIS.value:
                session.final_diagnosis = action_content.get("diagnosis", "Unknown diagnosis")
                session.confidence_score = action_content.get("confidence", 0.0)
                session.add_trace(
                    ActionType.MAKE_DIAGNOSIS,
                    "Consensus Coordinator",
                    f"Final Diagnosis: {session.final_diagnosis}",
                    {
                        "confidence": session.confidence_score,
                        "reasoning": reasoning,
                        "panel_synthesis": consensus_result.get("panel_synthesis", ""),
                        "round": round_num + 1
                    }
                )
                break
                
            elif consensus_action == ActionType.ORDER_TESTS.value:
                # Execute ordered tests and incorporate results for next round
                tests_to_order = action_content.get("tests", [])
                test_results, test_costs = await self._simulate_test_execution(tests_to_order)
                accumulated_findings.extend(test_results)
                session.add_trace(
                    ActionType.ORDER_TESTS,
                    "Consensus Coordinator",
                    f"Ordered tests: {', '.join(tests_to_order)} (Total cost: ${test_costs:.2f})",
                    {
                        "tests": tests_to_order,
                        "reasoning": reasoning,
                        "panel_synthesis": consensus_result.get("panel_synthesis", ""),
                        "round": round_num + 1,
                        "test_costs": test_costs
                    },
                    cost_impact=test_costs
                )
                
            elif consensus_action == ActionType.ASK_QUESTIONS.value:
                # Ask questions and incorporate answers for next round
                questions_to_ask = action_content.get("questions", [])
                question_results, visit_cost = await self._simulate_question_answers(questions_to_ask)
                accumulated_findings.extend(question_results)
                session.add_trace(
                    ActionType.ASK_QUESTIONS,
                    "Consensus Coordinator",
                    f"Asked questions: {'; '.join(questions_to_ask)}" + (f" (Visit cost: ${visit_cost:.2f})" if visit_cost > 0 else ""),
                    {
                        "questions": questions_to_ask,
                        "reasoning": reasoning,
                        "panel_synthesis": consensus_result.get("panel_synthesis", ""),
                        "round": round_num + 1,
                        "visit_cost": visit_cost
                    },
                    cost_impact=visit_cost if visit_cost > 0 else None
                )
            
            else:
                # Fallback - if consensus action is not recognized, default to ask questions
                fallback_results, fallback_cost = await self._simulate_question_answers([
                    "What additional information would help with diagnosis?"
                ])
                accumulated_findings.extend(fallback_results)
                session.add_trace(
                    ActionType.ASK_QUESTIONS,
                    "Consensus Coordinator",
                    f"Unrecognized consensus action '{consensus_action}', defaulting to questions" + (f" (Visit cost: ${fallback_cost:.2f})" if fallback_cost > 0 else ""),
                    {
                        "questions": ["What additional information would help with diagnosis?"],
                        "reasoning": f"Consensus coordinator returned unrecognized action: {consensus_action}",
                        "consensus_result": consensus_result,
                        "round": round_num + 1,
                        "visit_cost": fallback_cost
                    },
                    cost_impact=fallback_cost if fallback_cost > 0 else None
                )
            
            # Round complete - new findings will be processed in next round's deliberation
        
        # Session completed - final diagnosis should have been made in the loop
        
        return session
    
    async def _execute_panel_deliberation(self, session: CaseExecutionSession, 
                                        case_info: str, findings: List[str],
                                        hypotheses: List[DiagnosticHypothesis]) -> Dict[str, Any]:
        """Execute single-stage panel deliberation where each agent contributes once"""
        
        contributions = {}
        
        # Each agent contributes once with full analysis and recommendations
        
        # Dr. Hypothesis provides differential diagnosis with probabilities
        hypothesis_contrib = await self.dr_hypothesis.contribute(
            case_info, findings, hypotheses, session
        )
        contributions["hypothesis"] = hypothesis_contrib
        current_hypotheses = self._parse_hypotheses_from_response(hypothesis_contrib)
        
        # Dr. Test-Chooser recommends tests based on current hypotheses
        test_contrib = await self.dr_test_chooser.contribute(
            case_info, findings, current_hypotheses, session
        )
        contributions["tests"] = test_contrib
        
        # Dr. Challenger identifies potential issues with current thinking
        challenge_contrib = await self.dr_challenger.contribute(
            case_info, findings, current_hypotheses, session
        )
        contributions["challenges"] = challenge_contrib
        
        # Dr. Stewardship reviews cost-effectiveness
        stewardship_contrib = await self.dr_stewardship.contribute(
            case_info, findings, current_hypotheses, session,
            self._parse_test_recommendations(test_contrib)
        )
        contributions["stewardship"] = stewardship_contrib
        
        # Dr. Checklist performs quality control assessment
        checklist_contrib = await self.dr_checklist.contribute(
            case_info, findings, current_hypotheses, session
        )
        contributions["checklist"] = checklist_contrib
        
        return contributions


    
    def _format_hypotheses_for_context(self, hypotheses: List[DiagnosticHypothesis]) -> str:
        """Format hypotheses for context in agent deliberation"""
        if not hypotheses:
            return "No current hypotheses"
        
        formatted = []
        for i, hyp in enumerate(hypotheses[:3], 1):
            formatted.append(f"{i}. {hyp.condition} ({hyp.probability:.2f}) - {hyp.reasoning[:100]}...")
        
        return "\n".join(formatted)
    
    async def _simulate_test_execution(self, tests: List[Union[str, Dict[str, Any]]]) -> Tuple[List[str], float]:
        """Simulate execution of diagnostic tests and return mock results with cost tracking"""
        results = []
        total_round_cost = 0.0
        
        for test in tests:
            # Handle both string test names and dictionary test objects
            if isinstance(test, str):
                test_name = test
            else:
                test_name = test.get("test_name", "Unknown test")
            
            # Calculate and track cost
            test_cost = cost_estimator.estimate_test_cost(test_name)
            total_round_cost += test_cost.total_cost
            
            # Mock test result - in real implementation, this would interface with actual systems
            result = f"{test_name}: [Simulated result - would be actual lab/imaging result] (Cost: ${test_cost.total_cost:.2f})"
            results.append(result)
        
        # Return both results and total cost for proper session tracking
        return results, total_round_cost
    
    async def _simulate_question_answers(self, questions: List[str]) -> Tuple[List[str], float]:
        """Simulate answers to patient questions with visit cost tracking"""
        answers = []
        visit_cost = 0.0
        
        # Questions are part of physician visit - add visit cost only once per case
        if hasattr(self, '_current_session') and not hasattr(self._current_session, '_visit_cost_added'):
            visit_cost = cost_estimator.PHYSICIAN_VISIT_COST
            self._current_session._visit_cost_added = True
        
        for question in questions:
            # Mock answer - in real implementation, this would interface with patient records
            answer = f"Q: {question} A: [Simulated patient response]"
            answers.append(answer)
        
        return answers, visit_cost
    
    def _parse_hypotheses_from_response(self, response: Dict[str, Any]) -> List[DiagnosticHypothesis]:
        """Parse agent response into DiagnosticHypothesis objects"""
        hypotheses = []
        for hyp_data in response.get("hypotheses", []):
            hypothesis = DiagnosticHypothesis(
                condition=hyp_data.get("condition", "Unknown"),
                probability=hyp_data.get("probability", 0.0),
                reasoning=hyp_data.get("reasoning", ""),
                supporting_evidence=hyp_data.get("supporting_evidence", []),
                contradictory_evidence=hyp_data.get("contradictory_evidence", [])
            )
            hypotheses.append(hypothesis)
        return sorted(hypotheses, key=lambda x: x.probability, reverse=True)
    
    def _parse_test_recommendations(self, test_response: Dict[str, Any]) -> List[TestRecommendation]:
        """Parse test recommendations from agent response"""
        recommendations = []
        for test_data in test_response.get("recommended_tests", []):
            rec = TestRecommendation(
                test_name=test_data.get("test_name", ""),
                rationale=test_data.get("rationale", ""),
                estimated_cost=test_data.get("estimated_cost"),
                priority=test_data.get("priority", 1),
                discriminative_value=test_data.get("discriminative_value", "")
            )
            recommendations.append(rec)
        return recommendations
    
    async def _instant_diagnosis(self, session: CaseExecutionSession, case_info: str) -> CaseExecutionSession:
        """Instant diagnosis mode - diagnosis based solely on initial vignette"""
        hypothesis_result = await self.dr_hypothesis.contribute(case_info, [], [], session)
        hypotheses = self._parse_hypotheses_from_response(hypothesis_result)
        
        if hypotheses:
            session.final_diagnosis = hypotheses[0].condition
            session.confidence_score = hypotheses[0].probability
        else:
            session.final_diagnosis = "Insufficient information for diagnosis"
            session.confidence_score = 0.1
            
        session.add_trace(
            ActionType.MAKE_DIAGNOSIS,
            "Dr. Hypothesis",
            f"Instant diagnosis: {session.final_diagnosis}",
            {"confidence": session.confidence_score}
        )
        
        return session
    
    async def _questions_only_mode(self, session: CaseExecutionSession, case_info: str) -> CaseExecutionSession:
        """Questions-only mode - can ask questions but cannot order diagnostic tests"""
        # Simulate asking questions and getting responses
        questions = [
            "Can you provide more details about the patient's symptoms?",
            "What is the patient's relevant medical history?",
            "What are the current vital signs and physical exam findings?"
        ]
        
        # Simulate getting additional information
        findings, visit_cost = await self._simulate_question_answers(questions)
        
        # Add trace with proper cost tracking
        session.add_trace(
            ActionType.ASK_QUESTIONS, 
            "System", 
            f"Questions-only mode: gathering additional history (Cost: ${visit_cost:.2f})",
            {"questions": questions, "visit_cost": visit_cost},
            cost_impact=visit_cost
        )
        
        # Generate diagnosis based on questions
        hypothesis_result = await self.dr_hypothesis.contribute(case_info, findings, [], session)
        hypotheses = self._parse_hypotheses_from_response(hypothesis_result)
        
        if hypotheses:
            session.final_diagnosis = hypotheses[0].condition
            session.confidence_score = hypotheses[0].probability
        else:
            session.final_diagnosis = "Insufficient information for diagnosis"
            session.confidence_score = 0.1
            
        session.add_trace(
            ActionType.MAKE_DIAGNOSIS,
            "Panel Consensus",
            f"Questions-only diagnosis: {session.final_diagnosis}"
        )
        
        return session
    
    def get_session_traces(self, case_id: str) -> List[ExecutionTrace]:
        """Get execution traces for a specific case"""
        if case_id in self.active_sessions:
            return self.active_sessions[case_id].traces
        return []
    
    def get_session_summary(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of a diagnostic session"""
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
            "created_at": session.created_at.isoformat(),
            "trace_count": len(session.traces),
            "agent_message_count": len(session.agent_messages)
        }