import json
import prompty
import prompty.azure
from prompty.tracer import trace, Tracer, console_tracer, PromptyTracer
from pathlib import Path

class Summarizer:
    def __init__(self, cosmosDBHelper: "cosmosdb_helper.CosmosDBHelper"):
        """
        Initialize Summarizer with a CosmosDBHelper instance.
        """
        try:
            Tracer.add("console", console_tracer)
            json_tracer = PromptyTracer()
            Tracer.add("PromptyTracer", json_tracer.tracer)
            self.cosmosDBHelper = cosmosDBHelper
        except Exception as e:
            raise ConnectionError(f"Unexpected error connecting to Cosmos DB: {e}")

    @trace
    def summarize_patient(self, patient_id: str) -> str:
        """        
        Gets patient info from database, then passes it to prompty for summarization.
        """
        patient_data = self.cosmosDBHelper.get_patient(patient_id)
        # Ensure patient_data is a dict and not a string
        if isinstance(patient_data, str):
            patient_data = json.loads(patient_data)

        result = prompty.execute("summarizer.prompty", inputs={"patient_data": patient_data})
        
        print(f"Summarization result for {patient_id}: {result}")
        
        # Parse the result as JSON if it's a string to ensure proper formatting
        rounds_data = {}
        if isinstance(result, str):
            try:
                # Clean the result string - remove markdown code block syntax
                cleaned_result = result.strip()
                if cleaned_result.startswith("```json"):
                    cleaned_result = cleaned_result[7:]  # Remove ```json
                if cleaned_result.startswith("```"):
                    cleaned_result = cleaned_result[3:]   # Remove ```
                if cleaned_result.endswith("```"):
                    cleaned_result = cleaned_result[:-3]  # Remove trailing ```
                
                cleaned_result = cleaned_result.strip()
                print(f"Cleaned result for parsing: {cleaned_result}")
                
                rounds_data = json.loads(cleaned_result)
                print(f"Successfully parsed JSON: {rounds_data}")
                
            except json.JSONDecodeError as e:
                print(f"JSON parsing failed: {e}")
                print(f"Attempted to parse: {cleaned_result}")
                # If parsing fails, treat as plain text and create empty structure
                rounds_data = {
                    "subjective": "",
                    "objective": "",
                    "assessment": "",
                    "plan": ""
                }
        elif isinstance(result, dict):
            rounds_data = result
        else:
            rounds_data = {
                "subjective": "",
                "objective": "",
                "assessment": "",
                "plan": ""
            }
        
        # Ensure all required fields exist in the rounds object
        required_fields = ["subjective", "objective", "assessment", "plan"]
        for field in required_fields:
            if field not in rounds_data:
                rounds_data[field] = ""
        
        # Create the final rounds object with proper structure
        patient_data["rounds"] = {
            "subjective": rounds_data.get("subjective", ""),
            "objective": rounds_data.get("objective", ""),
            "assessment": rounds_data.get("assessment", ""),
            "plan": rounds_data.get("plan", "")
        }
        self.cosmosDBHelper.save_patient_data(patient_id, patient_data)
        pass
