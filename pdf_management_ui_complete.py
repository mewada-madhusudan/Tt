from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QListWidget, QListWidgetItem, QProgressBar, QCheckBox,
                             QMessageBox, QWidget, QGroupBox, QScrollArea, QFormLayout)
from PyQt6.QtCore import Qt, QSize, QThreadPool
from PyQt6.QtGui import QIcon, QColor
from pdf_conversion_worker import PDFConversionWorker, BatchConversionWorker
import os

class DocumentListItem(QWidget):
    """
    Custom widget for displaying document with status in a list
    """
    def __init__(self, doc_data, parent=None):
        super().__init__(parent)
        self.doc_id = doc_data["id"]
        self.doc_data = doc_data
        
        # Main layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # Document info layout
        info_layout = QVBoxLayout()
        
        # Document name
        self.name_label = QLabel(doc_data["original_filename"])
        self.name_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.name_label)
        
        # Status info
        status_layout = QHBoxLayout()
        
        status_text = doc_data["conversion_status"].replace("_", " ").title()
        status_color = self._get_status_color(doc_data["conversion_status"])
        
        self.status_label = QLabel(f"Status: {status_text}")
        self.status_label.setStyleSheet(f"color: {status_color}")
        status_layout.addWidget(self.status_label)
        
        # Add page count if available
        if doc_data["page_count"] and doc_data["page_count"] > 0:
            self.pages_label = QLabel(f"Pages: {doc_data['page_count']}")
            status_layout.addWidget(self.pages_label)
        
        info_layout.addLayout(status_layout)
        
        # Add progress bar for conversion
        if doc_data["is_scanned"] and doc_data["conversion_status"] in ["pending", "in_progress"]:
            self.progress_bar = QProgressBar()
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(int(doc_data["conversion_progress"] or 0))
            info_layout.addWidget(self.progress_bar)
        
        self.layout.addLayout(info_layout)
        
        # Add convert button for scanned documents that need conversion
        if doc_data["is_scanned"] and doc_data["conversion_status"] in ["pending", "failed"]:
            self.convert_btn = QPushButton("Convert")
            self.convert_btn.clicked.connect(self.on_convert_clicked)
            self.layout.addWidget(self.convert_btn)
        
        # Add spacer to push content to the left
        self.layout.addStretch()
    
    def _get_status_color(self, status):
        """Get appropriate color for status text"""
        status_colors = {
            "pending": "#FF9800",  # Orange
            "in_progress": "#2196F3",  # Blue
            "completed": "#4CAF50",  # Green
            "failed": "#F44336",  # Red
            "not_required": "#9E9E9E"  # Gray
        }
        return status_colors.get(status, "#000000")
    
    def update_progress(self, progress):
        """Update progress bar value"""
        if hasattr(self, "progress_bar"):
            self.progress_bar.setValue(int(progress))
    
    def update_status(self, status, progress=None):
        """Update status label and progress"""
        status_text = status.replace("_", " ").title()
        status_color = self._get_status_color(status)
        self.status_label.setText(f"Status: {status_text}")
        self.status_label.setStyleSheet(f"color: {status_color}")
        
        if progress is not None and hasattr(self, "progress_bar"):
            self.progress_bar.setValue(int(progress))
    
    def on_convert_clicked(self):
        """Handle convert button click"""
        # This will be connected to the parent dialog's convert method
        pass


class PDFManagementDialog(QDialog):
    """
    Dialog for managing PDF documents in knowledge bases
    """
    def __init__(self, llm_processor, parent=None):
        super().__init__(parent)
        self.llm_processor = llm_processor
        self.thread_pool = QThreadPool()
        self.document_widgets = {}  # Store widgets by doc_id for updates
        
        self.setWindowTitle("PDF Document Management")
        self.setMinimumSize(700, 500)
        
        self.setup_ui()
        self.load_knowledge_bases()
    
    def setup_ui(self):
        """Setup the dialog UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Knowledge base selector
        kb_layout = QHBoxLayout()
        kb_layout.addWidget(QLabel("Knowledge Base:"))
        self.kb_combo = QComboBox()
        self.kb_combo.currentIndexChanged.connect(self.on_kb_changed)
        kb_layout.addWidget(self.kb_combo)
        
        # Add KB button
        self.add_kb_btn = QPushButton("Add New KB")
        self.add_kb_btn.clicked.connect(self.on_add_kb_clicked)
        kb_layout.addWidget(self.add_kb_btn)
        
        main_layout.addLayout(kb_layout)
        
        # Document list
        doc_group = QGroupBox("Documents")
        doc_layout = QVBoxLayout(doc_group)
        
        self.document_list = QListWidget()
        self.document_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.document_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        doc_layout.addWidget(self.document_list)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.add_doc_btn = QPushButton("Add Document")
        self.add_doc_btn.clicked.connect(self.on_add_document_clicked)
        action_layout.addWidget(self.add_doc_btn)
        
        self.batch_convert_btn = QPushButton("Batch Convert")
        self.batch_convert_btn.clicked.connect(self.on_batch_convert_clicked)
        action_layout.addWidget(self.batch_convert_btn)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_document_list)
        action_layout.addWidget(self.refresh_btn)
        
        doc_layout.addLayout(action_layout)
        main_layout.addWidget(doc_group)
        
        # Close button
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.close_btn)
        main_layout.addLayout(buttons_layout)
    
    def load_knowledge_bases(self):
        """Load available knowledge bases into combo box"""
        self.kb_combo.clear()
        kb_list = self.llm_processor.get_kb_list()
        
        if kb_list:
            self.kb_combo.addItems(kb_list)
        else:
            # No KBs available
            self.document_list.clear()
            self.add_doc_btn.setEnabled(False)
            self.batch_convert_btn.setEnabled(False)
    
    def on_kb_changed(self, index):
        """Handle knowledge base selection change"""
        if index >= 0:
            kb_name = self.kb_combo.currentText()
            self.refresh_document_list()
            self.add_doc_btn.setEnabled(True)
            self.batch_convert_btn.setEnabled(True)
        else:
            self.document_list.clear()
            self.add_doc_btn.setEnabled(False)
            self.batch_convert_btn.setEnabled(False)
    
    def refresh_document_list(self):
        """Refresh the document list for current KB"""
        kb_name = self.kb_combo.currentText()
        if not kb_name:
            return
        
        # Clear previous document list
        self.document_list.clear()
        self.document_widgets = {}
        
        # Get documents for current KB
        documents = self.llm_processor.get_kb_documents(kb_name)
        
        for doc in documents:
            # Create list item
            item = QListWidgetItem()
            item.setSizeHint(QSize(self.document_list.width(), 80))  # Height depends on content
            
            # Create widget for document display
            doc_widget = DocumentListItem(doc)
            # Connect convert button if exists
            if hasattr(doc_widget, "convert_btn"):
                doc_widget.convert_btn.clicked.connect(
                    lambda checked, doc_id=doc["id"]: self.start_conversion(doc_id)
                )
            
            # Store widget reference
            self.document_widgets[doc["id"]] = doc_widget
            
            # Add to list
            self.document_list.addItem(item)
            self.document_list.setItemWidget(item, doc_widget)
    
    def on_add_kb_clicked(self):
        """Handle add knowledge base button click"""
        kb_name, ok = QInputDialog.getText(self, "Add Knowledge Base", "KB Name:")
        
        if ok and kb_name:
            # Create KB
            success = self.llm_processor.create_kb(kb_name)
            
            if success:
                # Refresh KB list
                self.load_knowledge_bases()
                # Select the new KB
                index = self.kb_combo.findText(kb_name)
                if index >= 0:
                    self.kb_combo.setCurrentIndex(index)
            else:
                QMessageBox.warning(self, "Error", "Failed to create knowledge base. Name may already exist.")
    
    def on_add_document_clicked(self):
        """Handle add document button click"""
        kb_name = self.kb_combo.currentText()
        if not kb_name:
            return
        
        # Open file dialog to select PDFs
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Documents", "", "PDF Files (*.pdf)"
        )
        
        if not files:
            return
        
        # Ask if these are scanned documents
        is_scanned = QMessageBox.question(
            self, "Document Type",
            "Are these scanned documents that need OCR?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes
        
        # Add documents to KB
        added_docs = []
        for file_path in files:
            doc_id = self.llm_processor.add_document_to_kb(kb_name, file_path, is_scanned)
            if doc_id:
                added_docs.append(doc_id)
        
        # Refresh document list
        self.refresh_document_list()
        
        # Ask if user wants to start conversion for scanned documents
        if is_scanned and added_docs:
            start_conversion = QMessageBox.question(
                self, "Start Conversion",
                "Do you want to start converting the added documents now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes
            
            if start_conversion:
                for doc_id in added_docs:
                    self.start_conversion(doc_id)
    
    def start_conversion(self, doc_id):
        """Start conversion for a specific document"""
        # Get document info
        doc = self.llm_processor.db_manager.get_document_by_id(doc_id)
        if not doc:
            return
        
        # Get KB info 
        kb = self.llm_processor.db_manager.get_knowledge_base_by_id(doc["kb_id"])
        if not kb:
            return
        
        # Set up output directory
        output_dir = os.path.join(kb["directory"], "converted")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Update status to in_progress
        self.llm_processor.update_document_conversion(doc_id, "in_progress", progress=0)
        if doc_id in self.document_widgets:
            self.document_widgets[doc_id].update_status("in_progress", 0)
        
        # Create worker for conversion
        worker = PDFConversionWorker(doc_id, doc["original_path"], output_dir)
        
        # Connect signals
        worker.signals.progress.connect(self.on_conversion_progress)
        worker.signals.completed.connect(self.on_conversion_completed)
        worker.signals.error.connect(self.on_conversion_error)
        
        # Start conversion
        self.thread_pool.start(worker)
    
    def on_batch_convert_clicked(self):
        """Start batch conversion for all pending documents"""
        # Get current KB
        kb_name = self.kb_combo.currentText()
        if not kb_name:
            return
        
        # Create batch worker
        base_dir = os.path.dirname(self.llm_processor.base_dir)
        worker = BatchConversionWorker(self.llm_processor.db_manager, base_dir)
        
        # Connect signals
        worker.signals.progress.connect(self.on_conversion_progress)
        worker.signals.completed.connect(self.on_conversion_completed)
        worker.signals.error.connect(self.on_conversion_error)
        
        # Start batch processing
        self.thread_pool.start(worker)
    
    def on_conversion_progress(self, doc_id, progress):
        """Handle conversion progress update"""
        # Update database
        self.llm_processor.update_document_conversion(doc_id, "in_progress", progress=progress)
        
        # Update UI
        if doc_id in self.document_widgets:
            self.document_widgets[doc_id].update_progress(progress)
    
    def on_conversion_completed(self, doc_id, output_path, page_count):
        """Handle conversion completion"""
        # Update database
        self.llm_processor.update_document_conversion(
            doc_id, "completed", progress=100,
            converted_path=output_path, page_count=page_count
        )
        
        # Update UI
        if doc_id in self.document_widgets:
            self.document_widgets[doc_id].update_status("completed", 100)
    
    def on_conversion_error(self, doc_id, error_msg):
        """Handle conversion error"""
        # Update database
        self.llm_processor.update_document_conversion(doc_id, "failed", progress=0)
        
        # Update UI
        if doc_id in self.document_widgets:
            self.document_widgets[doc_id].update_status("failed", 0)
        
        # Show error message
        QMessageBox.warning(self, "Conversion Error", f"Error converting document: {error_msg}")


class QComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)


class QInputDialog:
    @staticmethod
    def getText(parent, title, label):
        from PyQt6.QtWidgets import QInputDialog
        return QInputDialog.getText(parent, title, label)


class QFileDialog:
    @staticmethod
    def getOpenFileNames(parent, caption, directory, filter):
        from PyQt6.QtWidgets import QFileDialog
        return QFileDialog.getOpenFileNames(parent, caption, directory, filter)
