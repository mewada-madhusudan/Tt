import os
import sys
import uuid
from db_manager import DBManager

class LLMProcessor:
    def __init__(self, db_path="app_data.db"):
        """
        Initialize the LLM processor with database connection
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_manager = DBManager(db_path)
        self.base_dir = "uploads"
        
        # Create base directory if it doesn't exist
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
    
    def close(self):
        """Close database connection"""
        self.db_manager.close()
    
    def create_kb(self, kb_name):
        """
        Create a new knowledge base directory and register in database
        
        Args:
            kb_name (str): Name of the knowledge base
            
        Returns:
            bool: True if successful, False otherwise
        """
        kb_dir = os.path.join(self.base_dir, kb_name)
        if not os.path.exists(kb_dir):
            os.makedirs(kb_dir)
            os.makedirs(os.path.join(kb_dir, "converted"), exist_ok=True)
            
            # Add to database
            kb_id = self.db_manager.add_knowledge_base(kb_name, kb_dir)
            return kb_id is not None
        return False
    
    def add_document_to_kb(self, kb_name, file_path, is_scanned=False):
        """
        Add a document to the specified knowledge base
        
        Args:
            kb_name (str): Name of the knowledge base
            file_path (str): Path to the document file
            is_scanned (bool): Whether the document is a scanned PDF
            
        Returns:
            int: Document ID if successful, None otherwise
        """
        # Get KB ID
        kb_id = self.db_manager.get_knowledge_base_id(kb_name)
        if not kb_id:
            return None
        
        kb_dir = self.get_kb_directory(kb_name)
        file_name = os.path.basename(file_path)
        destination = os.path.join(kb_dir, file_name)
        
        try:
            # Copy file to KB directory
            with open(file_path, 'rb') as src_file:
                with open(destination, 'wb') as dst_file:
                    dst_file.write(src_file.read())
            
            # Add to database
            doc_id = self.db_manager.add_document(
                kb_id, file_name, destination, is_scanned
            )
            
            return doc_id
        except Exception as e:
            print(f"Error copying file: {e}")
            return None
    
    def get_kb_directory(self, kb_name):
        """Get the directory path for a knowledge base"""
        kb_id = self.db_manager.get_knowledge_base_id(kb_name)
        if kb_id:
            kb = self.db_manager.get_knowledge_base_by_id(kb_id)
            return kb["directory"]
        return None
    
    def get_kb_files(self, kb_name):
        """
        Get list of files in a knowledge base (prioritizing converted files)
        
        Args:
            kb_name (str): Name of the knowledge base
            
        Returns:
            list: List of file paths
        """
        kb_id = self.db_manager.get_knowledge_base_id(kb_name)
        if not kb_id:
            return []
        
        documents = self.db_manager.get_documents_by_kb(kb_id)
        files = []
        
        for doc in documents:
            # Use converted path if available, otherwise use original
            if doc["converted_path"] and os.path.exists(doc["converted_path"]):
                files.append(doc["converted_path"])
            elif os.path.exists(doc["original_path"]):
                files.append(doc["original_path"])
        
        return files
    
    def get_kb_list(self):
        """
        Get list of available knowledge bases
        
        Returns:
            list: List of knowledge base names
        """
        kbs = self.db_manager.get_all_knowledge_bases()
        return [kb["name"] for kb in kbs]
    
    def get_pending_conversions(self):
        """Get list of documents pending conversion"""
        return self.db_manager.get_pending_conversions()
    
    def get_kb_documents(self, kb_name):
        """
        Get all documents for a knowledge base with their status
        
        Args:
            kb_name (str): Name of the knowledge base
            
        Returns:
            list: List of document dictionaries
        """
        kb_id = self.db_manager.get_knowledge_base_id(kb_name)
        if not kb_id:
            return []
        
        return self.db_manager.get_documents_by_kb(kb_id)
    
    def update_document_conversion(self, doc_id, status, progress=None, converted_path=None, page_count=None):
        """Update document conversion status in the database"""
        self.db_manager.update_document_conversion(
            doc_id, status, progress, converted_path, page_count
        )
    
    def process_query(self, data_element, procedure, kb_name):
        """
        Process a query using the knowledge base
        
        Args:
            data_element (str): Data element to query
            procedure (str): Procedure to use
            kb_name (str): Knowledge base name
            
        Returns:
            dict: Result dictionary
        """
        try:
            # Get KB ID
            kb_id = self.db_manager.get_knowledge_base_id(kb_name)
            if not kb_id:
                return {"result": "Error: Knowledge base not found", "page": None, "conversation_id": None, "file": None}
            
            # Get files for the KB (prioritizing converted files)
            files = self.get_kb_files(kb_name)
            file_path = files[0] if files else None
            
            # This is a placeholder - replace with your actual LLM API call
            # In a real implementation, you would query against the files in the KB
            result = f"Result for {data_element} using {procedure} from KB: {kb_name}"
            page_number = 2  # Example page number
            
            # Generate a conversation ID
            conversation_id = f"conv_{uuid.uuid4().hex}"
            
            # Store conversation in database
            self.db_manager.add_conversation(conversation_id, data_element, procedure, kb_id)
            
            # Store initial query and response as messages
            query_message = f"{data_element} - {procedure}"
            self.db_manager.add_message(conversation_id, True, query_message)  # User query
            self.db_manager.add_message(conversation_id, False, result)  # System response
            
            return {
                "result": result, 
                "page": page_number, 
                "conversation_id": conversation_id,
                "file": file_path,
                "kb_name": kb_name
            }
        except Exception as e:
            print(f"Error processing query: {e}")
            return {
                "result": f"Error: {str(e)}", 
                "page": None, 
                "conversation_id": None, 
                "file": None, 
                "kb_name": kb_name
            }
    
    def follow_up_query(self, question, conversation_id):
        """
        Process a follow-up question using the existing conversation context
        
        Args:
            question (str): Follow-up question
            conversation_id (str): Conversation ID
            
        Returns:
            dict: Response dictionary
        """
        try:
            # Store user question in database
            self.db_manager.add_message(conversation_id, True, question)
            
            # This is a placeholder - replace with your actual follow-up API call
            response = f"Follow-up answer to: {question}"
            
            # Store system response in database
            self.db_manager.add_message(conversation_id, False, response)
            
            return {
                "response": response, 
                "conversation_id": conversation_id
            }
        except Exception as e:
            print(f"Error processing follow-up: {e}")
            return {
                "response": f"Error: {str(e)}", 
                "conversation_id": conversation_id
            }
    
    def get_conversation_history(self, conversation_id):
        """
        Get all messages for a conversation
        
        Args:
            conversation_id (str): Conversation ID
            
        Returns:
            list: List of message dictionaries
        """
        return self.db_manager.get_conversation_messages(conversation_id)