"""
MAI Diagnostic Orchestrator (MAI-DxO)

Implementation of the diagnostic orchestrator pattern from the Microsoft AI research paper,
featuring multi-agent coordination for clinical diagnosis with role-specialized reasoning agents.

This module provides:
- Multi-agent orchestration framework with 5 specialized medical roles
- Chain of debate coordination between agents
- Comprehensive execution tracing and decision logging
- Cost-aware diagnostic planning
- Integration with Azure AI Foundry and Semantic Kernel patterns
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

# Import cost estimation capabilities
from cost_estimator import cost_estimator, TestCost

# Trace and execution models
class ActionType(str, Enum):
    """Types of actions the diagnostic panel can take"""
    ASK_QUESTIONS = "ask_questions"
    ORDER_TESTS = "order_tests" 
    MAKE_DIAGNOSIS = "make_diagnosis"
    INTERNAL_DEBATE = "internal_debate"
    COST_ESTIMATION = "cost_estimation"

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
        self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
        
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
                        session: CaseExecutionSession,
                        proposed_actions: Dict[str, Any] = None) -> Dict[str, Any]:
        
        system_prompt = """You are Dr. Checklist, the quality control specialist ensuring systematic and thorough care.

Your role:
1. Validate that test names are specific and orderable
2. Check for internal consistency across agent recommendations
3. Ensure systematic approach to diagnosis
4. Flag any logical inconsistencies or gaps
5. Verify completeness of workup

Format your response as JSON:
{
    "validation_results": [
        {
            "item": "item being validated",
            "status": "valid / invalid / needs clarification",
            "issue": "description of any problems",
            "recommendation": "how to fix issues"
        }
    ],
    "consistency_check": "assessment of internal logic consistency",
    "completeness_assessment": "gaps in current diagnostic approach",
    "quality_score": 1-10
}"""

        actions_text = json.dumps(proposed_actions, indent=2) if proposed_actions else "No actions proposed."
        hypotheses_summary = "\n".join([f"- {h.condition} ({h.probability:.2f})" for h in current_hypotheses]) if current_hypotheses else "No hypotheses."
        
        user_message = f"""
Case: {case_info}

Proposed Actions:
{actions_text}

Current Hypotheses:
{hypotheses_summary}

Perform quality control validation on the proposed diagnostic approach.
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
            "validation_results": [],
            "consistency_check": response,
            "completeness_assessment": "Assessment pending",
            "quality_score": 5
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
        
        if not endpoint or not api_key:
            raise ValueError("Azure OpenAI endpoint and key must be provided")
            
        self.client = AsyncOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-02-15-preview"
        )
        
        # Initialize specialized agents
        self.dr_hypothesis = DrHypothesis(self.client)
        self.dr_test_chooser = DrTestChooser(self.client)
        self.dr_challenger = DrChallenger(self.client)
        self.dr_stewardship = DrStewardship(self.client)
        self.dr_checklist = DrChecklist(self.client)
        
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
            execution_mode: "instant", "questions_only", "budgeted", "unconstrained", "ensemble"
        
        Returns:
            CaseExecutionSession with complete execution trace
        """
        case_id = str(uuid.uuid4())
        session = CaseExecutionSession(case_id, case_info)
        self.active_sessions[case_id] = session
        self._current_session = session  # Store for cost tracking
        
        session.add_trace(
            ActionType.INTERNAL_DEBATE, 
            "System", 
            f"Starting diagnostic orchestration for case {case_id}",
            {"execution_mode": execution_mode, "budget_limit": budget_limit}
        )
        
        current_hypotheses: List[DiagnosticHypothesis] = []
        accumulated_findings: List[str] = []
        
        # Handle different execution modes
        if execution_mode == "instant":
            return await self._instant_diagnosis(session, case_info)
        elif execution_mode == "questions_only":
            return await self._questions_only_mode(session, case_info)
        
        # Main diagnostic loop
        for round_num in range(max_rounds):
            session.increment_round()
            self._visit_cost_added_this_round = False  # Reset visit cost flag per round
            
            session.add_trace(
                ActionType.INTERNAL_DEBATE,
                "System",
                f"=== DIAGNOSTIC ROUND {round_num + 1} ==="
            )
            
            # Execute chain of debate
            debate_result = await self._execute_chain_of_debate(
                session, case_info, accumulated_findings, current_hypotheses
            )
            
            # Check budget constraints
            if budget_limit and session.total_cost >= budget_limit:
                session.add_trace(
                    ActionType.COST_ESTIMATION,
                    "System",
                    f"Budget limit reached: ${session.total_cost:.2f} >= ${budget_limit:.2f}"
                )
                break
                
            # Determine next action based on debate outcome
            action = await self._determine_next_action(session, debate_result, current_hypotheses)
            
            if action["action"] == "diagnose":
                session.final_diagnosis = action["diagnosis"]
                session.confidence_score = action.get("confidence", 0.0)
                session.add_trace(
                    ActionType.MAKE_DIAGNOSIS,
                    "Panel Consensus",
                    f"Final Diagnosis: {session.final_diagnosis}",
                    {"confidence": session.confidence_score}
                )
                break
            elif action["action"] == "order_tests":
                # Simulate test execution and add results to findings
                test_results = await self._simulate_test_execution(action["tests"])
                accumulated_findings.extend(test_results)
            elif action["action"] == "ask_questions":
                # Simulate question answers and add to findings  
                question_results = await self._simulate_question_answers(action["questions"])
                accumulated_findings.extend(question_results)
                
            # Update hypotheses based on new findings
            if accumulated_findings:
                hypothesis_update = await self.dr_hypothesis.contribute(
                    case_info, accumulated_findings, current_hypotheses, session
                )
                current_hypotheses = self._parse_hypotheses_from_response(hypothesis_update)
        
        session.add_trace(
            ActionType.INTERNAL_DEBATE,
            "System", 
            f"Diagnostic session completed. Total cost: ${session.total_cost:.2f}"
        )
        
        return session
    
    async def _execute_chain_of_debate(self, session: CaseExecutionSession, 
                                     case_info: str, findings: List[str],
                                     hypotheses: List[DiagnosticHypothesis]) -> Dict[str, Any]:
        """Execute the structured deliberation between all agents"""
        
        session.add_trace(
            ActionType.INTERNAL_DEBATE,
            "System",
            "Initiating Chain of Debate between specialist agents"
        )
        
        # Collect contributions from each agent
        contributions = {}
        
        # Dr. Hypothesis updates differential
        hypothesis_contrib = await self.dr_hypothesis.contribute(
            case_info, findings, hypotheses, session
        )
        contributions["hypothesis"] = hypothesis_contrib
        
        # Dr. Test-Chooser recommends tests
        test_contrib = await self.dr_test_chooser.contribute(
            case_info, findings, hypotheses, session
        )
        contributions["tests"] = test_contrib
        
        # Dr. Challenger provides counterarguments
        challenge_contrib = await self.dr_challenger.contribute(
            case_info, findings, hypotheses, session
        )
        contributions["challenges"] = challenge_contrib
        
        # Dr. Stewardship reviews costs
        stewardship_contrib = await self.dr_stewardship.contribute(
            case_info, findings, hypotheses, session,
            self._parse_test_recommendations(test_contrib)
        )
        contributions["stewardship"] = stewardship_contrib
        
        # Dr. Checklist validates consistency
        checklist_contrib = await self.dr_checklist.contribute(
            case_info, findings, hypotheses, session, contributions
        )
        contributions["checklist"] = checklist_contrib
        
        session.add_trace(
            ActionType.INTERNAL_DEBATE,
            "Panel",
            "Chain of Debate completed",
            contributions
        )
        
        return contributions
    
    async def _determine_next_action(self, session: CaseExecutionSession,
                                   debate_result: Dict[str, Any],
                                   hypotheses: List[DiagnosticHypothesis]) -> Dict[str, Any]:
        """Determine the next action based on agent debate results"""
        
        # Simple consensus logic - can be enhanced
        confidence_threshold = 0.8
        
        if hypotheses and hypotheses[0].probability >= confidence_threshold:
            return {
                "action": "diagnose",
                "diagnosis": hypotheses[0].condition,
                "confidence": hypotheses[0].probability
            }
        
        # Check stewardship recommendations
        stewardship = debate_result.get("stewardship", {})
        if stewardship.get("budget_recommendation") == "stop and reassess":
            return {
                "action": "diagnose",
                "diagnosis": hypotheses[0].condition if hypotheses else "Insufficient data",
                "confidence": 0.5
            }
        
        # Default to ordering tests
        tests = debate_result.get("tests", {}).get("recommended_tests", [])
        if tests:
            return {
                "action": "order_tests", 
                "tests": tests[:2]  # Limit to 2 tests per round
            }
        
        # Fall back to asking questions
        return {
            "action": "ask_questions",
            "questions": ["What additional symptoms or findings are present?"]
        }
    
    async def _simulate_test_execution(self, tests: List[Dict[str, Any]]) -> List[str]:
        """Simulate execution of diagnostic tests and return mock results with cost tracking"""
        results = []
        total_round_cost = 0.0
        
        for test in tests:
            test_name = test.get("test_name", "Unknown test")
            
            # Calculate and track cost
            test_cost = cost_estimator.estimate_test_cost(test_name)
            total_round_cost += test_cost.total_cost
            
            # Mock test result - in real implementation, this would interface with actual systems
            result = f"{test_name}: [Simulated result - would be actual lab/imaging result] (Cost: ${test_cost.total_cost:.2f})"
            results.append(result)
        
        # Add cost trace
        if hasattr(self, '_current_session'):
            self._current_session.add_trace(
                ActionType.COST_ESTIMATION,
                "Cost Estimator",
                f"Tests ordered this round cost: ${total_round_cost:.2f}",
                {"test_costs": [{"test": t["test_name"], "cost": cost_estimator.estimate_test_cost(t["test_name"]).total_cost} for t in tests]},
                total_round_cost
            )
        
        return results
    
    async def _simulate_question_answers(self, questions: List[str]) -> List[str]:
        """Simulate answers to patient questions with visit cost tracking"""
        answers = []
        
        # Questions are part of physician visit - add visit cost if not already added this round
        if hasattr(self, '_current_session') and not hasattr(self, '_visit_cost_added_this_round'):
            self._current_session.add_trace(
                ActionType.COST_ESTIMATION,
                "Cost Estimator", 
                f"Physician visit cost: ${cost_estimator.PHYSICIAN_VISIT_COST:.2f}",
                {"visit_cost": cost_estimator.PHYSICIAN_VISIT_COST},
                cost_estimator.PHYSICIAN_VISIT_COST
            )
            self._visit_cost_added_this_round = True
        
        for question in questions:
            # Mock answer - in real implementation, this would interface with patient records
            answer = f"Q: {question} A: [Simulated patient response]"
            answers.append(answer)
        return answers
    
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
        
        session.add_trace(ActionType.ASK_QUESTIONS, "System", "Questions-only mode: gathering additional history")
        session.total_cost = 300  # Single physician visit cost
        
        # Simulate getting additional information
        findings = await self._simulate_question_answers(questions)
        
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