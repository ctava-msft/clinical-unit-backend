import pymongo
import json
from bson import ObjectId

class CosmosDBHelper:
    def __init__(self, connection_string: str, database_name: str, collection_name: str):
        """
        Initialize MongoClient using Cosmos DB Mongo API.
        """
        try:
            # Configure client with settings compatible with Cosmos DB wire version
            self.client = pymongo.MongoClient(
                connection_string, 
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=20000,
                socketTimeoutMS=20000,
                retryWrites=False,  # Cosmos DB doesn't support retryable writes
                w=1  # Write concern
            )
            # Test the connection with a simple operation
            self.client.admin.command('ping')
            mydb = self.client[database_name]
            self.collection = mydb[collection_name]
        except pymongo.errors.ServerSelectionTimeoutError as e:
            raise ConnectionError(f"Failed to connect to Cosmos DB - timeout: {e}")
        except pymongo.errors.ConfigurationError as e:
            # Handle wire version compatibility issues more gracefully
            if "wire version" in str(e):
                print(f"Warning: Wire version compatibility issue: {e}")
                # Try with a more permissive client configuration
                try:
                    self.client = pymongo.MongoClient(
                        connection_string,
                        serverSelectionTimeoutMS=30000,
                        retryWrites=False
                    )
                    mydb = self.client[database_name]
                    self.collection = mydb[collection_name]
                except Exception as retry_e:
                    raise ConnectionError(f"Connection failed even with compatibility mode: {retry_e}")
            else:
                raise ConnectionError(f"Invalid connection configuration: {e}")
        except Exception as e:
            raise ConnectionError(f"Unexpected error connecting to Cosmos DB: {e}")
        
    def get_patient_info(self, patient_id: str) -> str:
        """
        Fetch patient info given a patient_id.
        Returns the patient JSON as a string, or an error message.
        """        

        # Query for a single document matching patient_id
        doc = self.collection.find_one({"mrn": patient_id}, {"_id": 0})
        if not doc:
            return f"[No patient found with id: {patient_id}]"
        # Return the raw JSON document
        return json.dumps(doc)

    # Get a patient from the database
    def get_patient(self, patient_id: str) -> dict:
        """
        Fetch complete patient object from CosmosDB given a patient_id (MRN).
        Returns the patient document as a dict, or an error dict if not found.
        """
        try:
            # Include _id field in the returned document
            doc = self.collection.find_one({"mrn": patient_id})
            if not doc:
                return {"error": f"No patient found with MRN: {patient_id}"}
            
            # Convert ObjectId to string for JSON serialization
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            
            return doc
        except Exception as e:
            print(f"Error fetching patient {patient_id}: {e}")
            return {"error": f"Database error while fetching patient {patient_id}: {str(e)}"}
    
    def save_patient_data(self, patient_id: str, patient_data: dict):
        """Save complete patient data including demographics, predictions, and clinical rounds"""
        try:
            # Ensure the document has the correct structure for CosmosDB
            document = {
                "mrn": patient_id,  # Use mrn instead of id for consistency
                **patient_data
            }
            
            # Remove _id from patient_data if it exists to avoid conflicts
            if "_id" in document:
                del document["_id"]
            
            # Update or insert the document using mrn field
            self.collection.replace_one(
                {"mrn": patient_id},
                document,
                upsert=True
            )
            return True
        except Exception as e:
            print(f"Error saving patient data: {e}")
            raise