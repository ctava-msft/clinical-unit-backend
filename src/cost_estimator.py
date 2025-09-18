"""
Cost Estimation Module for MAI Diagnostic Orchestrator

This module provides cost estimation capabilities for diagnostic tests and procedures,
following the methodology described in the MAI-DxO research paper. It includes:
- CPT code mapping for diagnostic procedures
- Cost lookup from healthcare pricing data
- Budget tracking and management
- Cost-effectiveness analysis for diagnostic recommendations
"""

import re
import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

@dataclass
class TestCost:
    """Represents the cost breakdown for a diagnostic test"""
    test_name: str
    cpt_codes: List[str]
    base_cost: float
    facility_fee: float = 0.0
    professional_fee: float = 0.0
    total_cost: float = 0.0
    cost_category: str = "moderate"  # low, moderate, high, very_high
    
    def __post_init__(self):
        self.total_cost = self.base_cost + self.facility_fee + self.professional_fee
        self._categorize_cost()
    
    def _categorize_cost(self):
        """Categorize cost level based on total cost"""
        if self.total_cost < 100:
            self.cost_category = "low"
        elif self.total_cost < 500:
            self.cost_category = "moderate"
        elif self.total_cost < 2000:
            self.cost_category = "high"
        else:
            self.cost_category = "very_high"

class CostEstimator:
    """
    Handles cost estimation for diagnostic procedures following MAI-DxO methodology
    """
    
    # Standard physician visit cost
    PHYSICIAN_VISIT_COST = 300.0
    
    # Common diagnostic test costs (based on 2023 healthcare pricing data)
    DEFAULT_TEST_COSTS = {
        # Laboratory Tests
        "CBC": {"base_cost": 25, "cpt_codes": ["85025"]},
        "CMP": {"base_cost": 35, "cpt_codes": ["80053"]},
        "BMP": {"base_cost": 30, "cpt_codes": ["80048"]},
        "Lipid Panel": {"base_cost": 40, "cpt_codes": ["80061"]},
        "TSH": {"base_cost": 60, "cpt_codes": ["84443"]},
        "HbA1c": {"base_cost": 45, "cpt_codes": ["83036"]},
        "PT/INR": {"base_cost": 35, "cpt_codes": ["85610"]},
        "PTT": {"base_cost": 30, "cpt_codes": ["85730"]},
        "Urinalysis": {"base_cost": 25, "cpt_codes": ["81001"]},
        "Blood Culture": {"base_cost": 75, "cpt_codes": ["87040"]},
        "Troponin": {"base_cost": 85, "cpt_codes": ["84484"]},
        "BNP": {"base_cost": 150, "cpt_codes": ["83880"]},
        "D-Dimer": {"base_cost": 95, "cpt_codes": ["85379"]},
        "ESR": {"base_cost": 25, "cpt_codes": ["85652"]},
        "CRP": {"base_cost": 35, "cpt_codes": ["86140"]},
        
        # Imaging Studies
        "Chest X-ray": {"base_cost": 200, "facility_fee": 100, "cpt_codes": ["71045"]},
        "CT Chest": {"base_cost": 800, "facility_fee": 400, "cpt_codes": ["71250"]},
        "CT Chest with Contrast": {"base_cost": 1200, "facility_fee": 600, "cpt_codes": ["71260"]},
        "CT Abdomen": {"base_cost": 900, "facility_fee": 450, "cpt_codes": ["74150"]},
        "CT Abdomen/Pelvis": {"base_cost": 1100, "facility_fee": 550, "cpt_codes": ["74177"]},
        "CT Head": {"base_cost": 700, "facility_fee": 350, "cpt_codes": ["70450"]},
        "MRI Brain": {"base_cost": 1500, "facility_fee": 750, "cpt_codes": ["70551"]},
        "MRI Spine": {"base_cost": 1600, "facility_fee": 800, "cpt_codes": ["72148"]},
        "Ultrasound Abdomen": {"base_cost": 400, "facility_fee": 200, "cpt_codes": ["76700"]},
        "Echocardiogram": {"base_cost": 600, "facility_fee": 300, "cpt_codes": ["93306"]},
        "EKG": {"base_cost": 75, "facility_fee": 25, "cpt_codes": ["93000"]},
        
        # Specialized Procedures
        "Colonoscopy": {"base_cost": 1200, "facility_fee": 800, "professional_fee": 400, "cpt_codes": ["45378"]},
        "Upper Endoscopy": {"base_cost": 900, "facility_fee": 600, "professional_fee": 300, "cpt_codes": ["43235"]},
        "Biopsy": {"base_cost": 500, "facility_fee": 300, "professional_fee": 200, "cpt_codes": ["88305"]},
        "Bone Marrow Biopsy": {"base_cost": 1500, "facility_fee": 1000, "professional_fee": 500, "cpt_codes": ["38221"]},
        "Lumbar Puncture": {"base_cost": 800, "facility_fee": 400, "professional_fee": 400, "cpt_codes": ["62270"]},
        "Bronchoscopy": {"base_cost": 1800, "facility_fee": 1200, "professional_fee": 600, "cpt_codes": ["31622"]},
        
        # Cardiac Studies
        "Stress Test": {"base_cost": 800, "facility_fee": 400, "professional_fee": 200, "cpt_codes": ["93017"]},
        "Cardiac Catheterization": {"base_cost": 3000, "facility_fee": 2000, "professional_fee": 1000, "cpt_codes": ["93458"]},
        "Holter Monitor": {"base_cost": 300, "facility_fee": 150, "cpt_codes": ["93224"]},
        
        # Specialized Lab Tests
        "Tumor Markers": {"base_cost": 200, "cpt_codes": ["86304"]},
        "Hepatitis Panel": {"base_cost": 150, "cpt_codes": ["80074"]},
        "HIV Test": {"base_cost": 75, "cpt_codes": ["86703"]},
        "Autoimmune Panel": {"base_cost": 400, "cpt_codes": ["86235"]},
        "Genetic Testing": {"base_cost": 2000, "cpt_codes": ["81479"]},
    }
    
    def __init__(self):
        self.test_costs = self.DEFAULT_TEST_COSTS.copy()
        self._load_custom_pricing()
    
    def _load_custom_pricing(self):
        """Load custom pricing data if available"""
        pricing_file = Path(__file__).parent / "diagnostic_pricing.json"
        if pricing_file.exists():
            try:
                with open(pricing_file, 'r') as f:
                    custom_costs = json.load(f)
                    self.test_costs.update(custom_costs)
            except Exception as e:
                print(f"Warning: Could not load custom pricing data: {e}")
    
    def estimate_test_cost(self, test_name: str) -> TestCost:
        """
        Estimate the cost of a specific diagnostic test
        
        Args:
            test_name: Name of the diagnostic test
            
        Returns:
            TestCost object with detailed cost breakdown
        """
        # Normalize test name for lookup
        normalized_name = self._normalize_test_name(test_name)
        
        # Direct lookup first
        if normalized_name in self.test_costs:
            cost_data = self.test_costs[normalized_name]
            return TestCost(
                test_name=test_name,
                cpt_codes=cost_data.get("cpt_codes", []),
                base_cost=cost_data.get("base_cost", 0),
                facility_fee=cost_data.get("facility_fee", 0),
                professional_fee=cost_data.get("professional_fee", 0)
            )
        
        # Fuzzy matching for similar tests
        estimated_cost = self._fuzzy_cost_match(test_name)
        if estimated_cost:
            return estimated_cost
        
        # Fallback estimation based on test type
        return self._estimate_by_category(test_name)
    
    def _normalize_test_name(self, test_name: str) -> str:
        """Normalize test name for consistent lookup"""
        # Remove common prefixes/suffixes
        normalized = test_name.strip()
        normalized = re.sub(r'\b(order|obtain|get|test|lab|study)\b', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Common abbreviation mappings
        abbreviations = {
            "CBC": "CBC",
            "CMP": "CMP", 
            "BMP": "BMP",
            "CXR": "Chest X-ray",
            "CT": "CT",
            "MRI": "MRI",
            "US": "Ultrasound",
            "Echo": "Echocardiogram",
            "EKG": "EKG",
            "ECG": "EKG"
        }
        
        for abbrev, full_name in abbreviations.items():
            if abbrev.lower() in normalized.lower():
                return full_name
        
        return normalized
    
    def _fuzzy_cost_match(self, test_name: str) -> Optional[TestCost]:
        """Attempt fuzzy matching for similar test names"""
        test_lower = test_name.lower()
        
        # Keywords for different categories
        imaging_keywords = ["ct", "mri", "ultrasound", "x-ray", "scan", "imaging"]
        lab_keywords = ["blood", "serum", "plasma", "urine", "culture", "panel"]
        procedure_keywords = ["biopsy", "endoscopy", "puncture", "catheter"]
        
        if any(keyword in test_lower for keyword in imaging_keywords):
            if "ct" in test_lower:
                base_cost = 1000 if "contrast" in test_lower else 800
                return TestCost(
                    test_name=test_name,
                    cpt_codes=["74150"],
                    base_cost=base_cost,
                    facility_fee=base_cost * 0.5
                )
            elif "mri" in test_lower:
                return TestCost(
                    test_name=test_name,
                    cpt_codes=["70551"],
                    base_cost=1500,
                    facility_fee=750
                )
            elif "ultrasound" in test_lower or "us" in test_lower:
                return TestCost(
                    test_name=test_name,
                    cpt_codes=["76700"],
                    base_cost=400,
                    facility_fee=200
                )
            elif "x-ray" in test_lower or "xray" in test_lower:
                return TestCost(
                    test_name=test_name,
                    cpt_codes=["71045"],
                    base_cost=200,
                    facility_fee=100
                )
        
        elif any(keyword in test_lower for keyword in lab_keywords):
            return TestCost(
                test_name=test_name,
                cpt_codes=["80053"],
                base_cost=75,
                facility_fee=0
            )
        
        elif any(keyword in test_lower for keyword in procedure_keywords):
            if "biopsy" in test_lower:
                return TestCost(
                    test_name=test_name,
                    cpt_codes=["88305"],
                    base_cost=500,
                    facility_fee=300,
                    professional_fee=200
                )
        
        return None
    
    def _estimate_by_category(self, test_name: str) -> TestCost:
        """Provide fallback cost estimate based on general category"""
        # Default to moderate cost lab test
        return TestCost(
            test_name=test_name,
            cpt_codes=["99999"],  # Unknown CPT code
            base_cost=150,
            facility_fee=0,
            professional_fee=0
        )
    
    def estimate_multiple_tests(self, test_names: List[str]) -> List[TestCost]:
        """Estimate costs for multiple tests"""
        return [self.estimate_test_cost(name) for name in test_names]
    
    def calculate_total_cost(self, test_costs: List[TestCost], 
                           physician_visits: int = 1) -> Dict[str, float]:
        """
        Calculate total costs including physician visits
        
        Args:
            test_costs: List of TestCost objects
            physician_visits: Number of physician visits
            
        Returns:
            Dictionary with cost breakdown
        """
        total_test_cost = sum(tc.total_cost for tc in test_costs)
        visit_cost = physician_visits * self.PHYSICIAN_VISIT_COST
        
        return {
            "test_costs": total_test_cost,
            "physician_visits": visit_cost,
            "total_cost": total_test_cost + visit_cost,
            "cost_breakdown": {
                "tests": [
                    {
                        "name": tc.test_name,
                        "cost": tc.total_cost,
                        "category": tc.cost_category
                    }
                    for tc in test_costs
                ],
                "visits": {
                    "count": physician_visits,
                    "cost_per_visit": self.PHYSICIAN_VISIT_COST,
                    "total_visit_cost": visit_cost
                }
            }
        }
    
    def is_high_cost_test(self, test_name: str, threshold: float = 1000.0) -> bool:
        """Check if a test exceeds the high-cost threshold"""
        cost_estimate = self.estimate_test_cost(test_name)
        return cost_estimate.total_cost > threshold
    
    def suggest_cheaper_alternatives(self, test_name: str) -> List[Dict[str, any]]:
        """
        Suggest cheaper alternative tests that might provide similar diagnostic value
        
        Args:
            test_name: Name of the expensive test
            
        Returns:
            List of alternative test suggestions with cost comparisons
        """
        current_cost = self.estimate_test_cost(test_name)
        test_lower = test_name.lower()
        alternatives = []
        
        # CT alternatives
        if "ct" in test_lower and "contrast" in test_lower:
            non_contrast = test_name.replace("with contrast", "").replace("contrast", "").strip()
            alt_cost = self.estimate_test_cost(non_contrast)
            if alt_cost.total_cost < current_cost.total_cost:
                alternatives.append({
                    "alternative": non_contrast,
                    "cost_savings": current_cost.total_cost - alt_cost.total_cost,
                    "rationale": "Consider non-contrast CT first if contrast not essential"
                })
        
        # MRI alternatives
        if "mri" in test_lower:
            ct_alternative = test_name.replace("MRI", "CT").replace("mri", "CT")
            alt_cost = self.estimate_test_cost(ct_alternative)
            alternatives.append({
                "alternative": ct_alternative,
                "cost_savings": current_cost.total_cost - alt_cost.total_cost,
                "rationale": "CT may provide adequate information at lower cost"
            })
            
            # Ultrasound for some indications
            if "abdomen" in test_lower:
                alternatives.append({
                    "alternative": "Ultrasound Abdomen",
                    "cost_savings": current_cost.total_cost - self.estimate_test_cost("Ultrasound Abdomen").total_cost,
                    "rationale": "Ultrasound may be sufficient for initial evaluation"
                })
        
        # Specialized lab alternatives
        if any(term in test_lower for term in ["genetic", "molecular", "specialized"]):
            alternatives.append({
                "alternative": "Standard laboratory workup",
                "cost_savings": current_cost.total_cost - 200,
                "rationale": "Consider standard tests before specialized assays"
            })
        
        return alternatives

# Global cost estimator instance
cost_estimator = CostEstimator()