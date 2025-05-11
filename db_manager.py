import sqlite3
import os
import datetime

class DBManager:
    """
    Database manager for tracking knowledge bases, files and conversion status
    """
    def __init__(self, db_path="app_data.db"):
        """Initialize database connection and create tables if they don't exist"""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        """Create required tables if they don't exist"""
        # Knowledge Base table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            directory TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Document Files table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_id INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            original_path TEXT NOT NULL,
            converted_path TEXT,
            is_scanned BOOLEAN DEFAULT FALSE,
            conversion_status TEXT DEFAULT 'pending',  -- pending, in_progress, completed, failed
            conversion_progress REAL DEFAULT 0,
            page_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
        )
        ''')
        
        # Conversation history table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT UNIQUE NOT NULL,
            data_element TEXT NOT NULL, 
            procedure TEXT NOT NULL,
            kb_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
        )
        ''')
        
        # Messages in conversations
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            is_user BOOLEAN NOT NULL,  -- TRUE if from user, FALSE if from system
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE
        )
        ''')
        
        self.conn.commit()
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
    
    def add_knowledge_base(self, name, directory):
        """
        Add a new knowledge base
        
        Args:
            name (str): Name of the knowledge base
            directory (str): Path to the knowledge base directory
            
        Returns:
            int: ID of the created knowledge base or None if error
        """
        try:
            self.cursor.execute(
                "INSERT INTO knowledge_bases (name, directory) VALUES (?, ?)",
                (name, directory)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            # Name already exists
            return None
        except Exception as e:
            print(f"Error adding knowledge base: {e}")
            return None
    
    def get_knowledge_base_id(self, name):
        """Get KB ID by name"""
        self.cursor.execute("SELECT id FROM knowledge_bases WHERE name = ?", (name,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def get_knowledge_base_by_id(self, kb_id):
        """Get knowledge base details by ID"""
        self.cursor.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,))
        result = self.cursor.fetchone()
        if result:
            return {
                "id": result[0],
                "name": result[1],
                "directory": result[2],
                "created_at": result[3]
            }
        return None
    
    def get_all_knowledge_bases(self):
        """Get all knowledge bases"""
        self.cursor.execute("SELECT id, name, directory, created_at FROM knowledge_bases ORDER BY name")
        results = self.cursor.fetchall()
        
        knowledge_bases = []
        for row in results:
            kb = {
                "id": row[0],
                "name": row[1],
                "directory": row[2],
                "created_at": row[3]
            }
            knowledge_bases.append(kb)
        
        return knowledge_bases
    
    def add_document(self, kb_id, original_filename, original_path, is_scanned=False):
        """
        Add a document to the database
        
        Args:
            kb_id (int): Knowledge base ID
            original_filename (str): Original filename
            original_path (str): Path to the original file
            is_scanned (bool): Whether the document is a scanned PDF
            
        Returns:
            int: ID of the created document or None if error
        """
        try:
            self.cursor.execute(
                """INSERT INTO documents 
                   (kb_id, original_filename, original_path, is_scanned, conversion_status) 
                   VALUES (?, ?, ?, ?, ?)""",
                (kb_id, original_filename, original_path, is_scanned, 
                 'pending' if is_scanned else 'not_required')
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"Error adding document: {e}")
            return None
    
    def update_document_conversion(self, doc_id, status, progress=None, converted_path=None, page_count=None):
        """
        Update document conversion status
        
        Args:
            doc_id (int): Document ID
            status (str): Conversion status (pending, in_progress, completed, failed)
            progress (float, optional): Conversion progress (0-100)
            converted_path (str, optional): Path to the converted file
            page_count (int, optional): Number of pages in the document
        """
        query = "UPDATE documents SET conversion_status = ?"
        params = [status]
        
        if progress is not None:
            query += ", conversion_progress = ?"
            params.append(progress)
        
        if converted_path is not None:
            query += ", converted_path = ?"
            params.append(converted_path)
        
        if page_count is not None:
            query += ", page_count = ?"
            params.append(page_count)
        
        query += " WHERE id = ?"
        params.append(doc_id)
        
        self.cursor.execute(query, params)
        self.conn.commit()
    
    def get_documents_by_kb(self, kb_id):
        """Get all documents for a knowledge base"""
        self.cursor.execute("""
            SELECT id, original_filename, original_path, converted_path, 
                   is_scanned, conversion_status, conversion_progress, page_count
            FROM documents 
            WHERE kb_id = ?
            ORDER BY original_filename
        """, (kb_id,))
        
        results = self.cursor.fetchall()
        documents = []
        
        for row in results:
            doc = {
                "id": row[0],
                "original_filename": row[1],
                "original_path": row[2],
                "converted_path": row[3],
                "is_scanned": bool(row[4]),
                "conversion_status": row[5],
                "conversion_progress": row[6],
                "page_count": row[7]
            }
            documents.append(doc)
        
        return documents
    
    def get_document_by_id(self, doc_id):
        """Get document details by ID"""
        self.cursor.execute("""
            SELECT id, kb_id, original_filename, original_path, converted_path, 
                   is_scanned, conversion_status, conversion_progress, page_count
            FROM documents 
            WHERE id = ?
        """, (doc_id,))
        
        result = self.cursor.fetchone()
        if result:
            return {
                "id": result[0],
                "kb_id": result[1],
                "original_filename": result[2],
                "original_path": result[3],
                "converted_path": result[4],
                "is_scanned": bool(result[5]),
                "conversion_status": result[6],
                "conversion_progress": result[7],
                "page_count": result[8]
            }
        return None
    
    def get_pending_conversions(self):
        """Get all documents pending conversion"""
        self.cursor.execute("""
            SELECT d.id, d.original_filename, d.original_path, k.name as kb_name
            FROM documents d
            JOIN knowledge_bases k ON d.kb_id = k.id
            WHERE d.is_scanned = TRUE AND d.conversion_status = 'pending'
        """)
        
        results = self.cursor.fetchall()
        documents = []
        
        for row in results:
            doc = {
                "id": row[0],
                "original_filename": row[1],
                "original_path": row[2],
                "kb_name": row[3]
            }
            documents.append(doc)
        
        return documents
    
    def add_conversation(self, conversation_id, data_element, procedure, kb_id):
        """Add a new conversation"""
        try:
            self.cursor.execute(
                "INSERT INTO conversations (conversation_id, data_element, procedure, kb_id) VALUES (?, ?, ?, ?)",
                (conversation_id, data_element, procedure, kb_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding conversation: {e}")
            return False
    
    def add_message(self, conversation_id, is_user, message):
        """Add a message to a conversation"""
        try:
            self.cursor.execute(
                "INSERT INTO messages (conversation_id, is_user, message) VALUES (?, ?, ?)",
                (conversation_id, is_user, message)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding message: {e}")
            return False
    
    def get_conversation_messages(self, conversation_id):
        """Get all messages for a conversation"""
        self.cursor.execute("""
            SELECT is_user, message, timestamp
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp
        """, (conversation_id,))
        
        results = self.cursor.fetchall()
        messages = []
        
        for row in results:
            message = {
                "is_user": bool(row[0]),
                "message": row[1],
                "timestamp": row[2]
            }
            messages.append(message)
        
        return messages