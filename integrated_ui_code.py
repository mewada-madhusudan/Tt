import sys
import os
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTableView, QHeaderView,
                             QSplitter, QMessageBox, QLineEdit, QTextEdit, QFrame, 
                             QGridLayout, QSizePolicy, QComboBox, QDialog, QListWidget,
                             QListWidgetItem, QDialogButtonBox, QFormLayout, QAbstractItemView)
from PyQt6.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QColor, QFont, QPalette, QIcon, QPixmap
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView

# Import PDF management functionality
from pdf_management_ui_complete import PDFManagementContent
from pdf_conversion_worker import PDFConversionWorker, BatchConversionWorker


# Keep existing classes (LLMProcessor, ResultsTableModel, Worker classes, ModernFrame)
# [LLMProcessor class implementation remains the same]
# [ResultsTableModel class implementation remains the same]
# [Worker classes implementation remains the same]
# [ModernFrame class implementation remains the same]


# Main application class with integrated PDF management
class DocumentProcessorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.llm_processor = LLMProcessor()
        
        # Initialize UI
        self.setWindowTitle("LLM Document Processor")
        self.setGeometry(100, 100, 1280, 800)
        
        # Apply modern styling
        self.apply_styling()
        
        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)
        
        # Content area for dynamic UI elements
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Start with the main selection screen
        self.setup_main_ui()
        
        # Initialize other variables
        self.excel_data = None
        self.current_results = []
        self.current_conversation_id = None
        self.selected_row_index = -1
        
        # PDF Management content (initially hidden)
        self.pdf_management_content = PDFManagementContent(self.llm_processor, self)
        self.content_layout.addWidget(self.pdf_management_content)
        self.pdf_management_content.hide()
        
        # Process document content (initially hidden)
        self.process_content = QWidget()
        self.process_layout = QVBoxLayout(self.process_content)
        self.setup_process_content()
        self.content_layout.addWidget(self.process_content)
        self.process_content.hide()
        
        # Add content area to main layout
        self.main_layout.addWidget(self.content_area)
        
        # Show KB list initially
        self.show_kb_list()
        
        # Setup thread pool for background tasks
        self.threadpool = QThreadPool()
        
        # Track active content
        self.active_content = None

    def apply_styling(self):
        """Apply modern styling to the application"""
        # Same as before - styling code would go here
        pass

    def setup_main_ui(self):
        """Setup the main UI structure"""
        # App title
        title_label = QLabel("LLM Document Processor")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4; margin-bottom: 10px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title_label)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Process data button
        self.process_btn = QPushButton("Process Documents")
        self.process_btn.setMinimumHeight(50)
        self.process_btn.clicked.connect(self.show_process_content)
        buttons_layout.addWidget(self.process_btn)
        
        # PDF Management button
        self.pdf_mgmt_btn = QPushButton("Manage PDF Documents")
        self.pdf_mgmt_btn.setMinimumHeight(50)
        self.pdf_mgmt_btn.clicked.connect(self.toggle_pdf_management)
        self.pdf_mgmt_btn.setStyleSheet("background-color: #8e44ad;")
        buttons_layout.addWidget(self.pdf_mgmt_btn)
        
        self.main_layout.addLayout(buttons_layout)

    def show_kb_list(self):
        """Show the knowledge base list in the main area"""
        # Clear existing layout
        self.clear_layout(self.content_layout)
        
        # Available KBs
        kb_list = self.llm_processor.get_kb_list()
        kb_frame = ModernFrame("Available Knowledge Bases")
        
        if kb_list:
            kb_list_widget = QListWidget()
            for kb in kb_list:
                item = QListWidgetItem(kb)
                kb_list_widget.addItem(item)
            kb_frame.layout.addWidget(kb_list_widget)
        else:
            no_kb_label = QLabel("No knowledge bases available. Use 'Manage PDF Documents' to create one.")
            kb_frame.layout.addWidget(no_kb_label)
        
        self.content_layout.addWidget(kb_frame)
        self.active_content = kb_frame

    def toggle_pdf_management(self):
        """Toggle the PDF management content visibility"""
        if self.pdf_management_content.isVisible():
            self.pdf_management_content.hide()
            self.show_kb_list()
            self.pdf_mgmt_btn.setStyleSheet("background-color: #8e44ad;")
        else:
            # Hide all other content
            if self.active_content:
                self.active_content.hide()
            if self.process_content.isVisible():
                self.process_content.hide()
            
            # Show PDF management
            self.pdf_management_content.show()
            self.pdf_management_content.refresh_content()  # Refresh the content
            self.active_content = self.pdf_management_content
            
            # Update button style to indicate it's active
            self.pdf_mgmt_btn.setStyleSheet("background-color: #663399;")
            self.process_btn.setStyleSheet("")

    def setup_process_content(self):
        """Setup the process document content"""
        # File selection group
        file_group = ModernFrame("Select Excel File")
        file_layout = QHBoxLayout()
        
        self.file_path_label = QLineEdit()
        self.file_path_label.setReadOnly(True)
        self.file_path_label.setPlaceholderText("No file selected")
        file_layout.addWidget(self.file_path_label, 4)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.load_excel)
        file_layout.addWidget(browse_btn, 1)
        
        file_group.layout.addLayout(file_layout)
        self.process_layout.addWidget(file_group)
        
        # KB selection group
        kb_group = ModernFrame("Select Knowledge Base")
        kb_layout = QHBoxLayout()
        
        self.kb_combo = QComboBox()
        kb_list = self.llm_processor.get_kb_list()
        self.kb_combo.addItems(kb_list)
        kb_layout.addWidget(self.kb_combo)
        
        kb_group.layout.addLayout(kb_layout)
        self.process_layout.addWidget(kb_group)
        
        # Process button
        process_btn = QPushButton("Process with LLM")
        process_btn.clicked.connect(self.process_data)
        process_btn.setMinimumHeight(40)
        self.process_layout.addWidget(process_btn)
        
        # Results area (initially empty)
        self.results_frame = ModernFrame("Results")
        self.results_layout = QVBoxLayout()
        self.results_frame.layout.addLayout(self.results_layout)
        self.process_layout.addWidget(self.results_frame)
        
        # Follow-up area (initially hidden)
        self.followup_frame = ModernFrame("Follow-up Questions")
        self.followup_layout = QVBoxLayout()
        
        # PDF viewer
        self.pdf_view = QPdfView()
        self.pdf_document = QPdfDocument()
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        
        # Follow-up input
        followup_input_layout = QHBoxLayout()
        self.followup_input = QLineEdit()
        self.followup_input.setPlaceholderText("Enter follow-up question...")
        followup_input_layout.addWidget(self.followup_input, 4)
        
        followup_btn = QPushButton("Send")
        followup_btn.clicked.connect(self.send_followup)
        followup_input_layout.addWidget(followup_btn, 1)
        
        # Follow-up response area
        self.followup_response = QTextEdit()
        self.followup_response.setReadOnly(True)
        
        # Add to layout
        self.followup_layout.addWidget(self.pdf_view, 4)
        self.followup_layout.addLayout(followup_input_layout)
        self.followup_layout.addWidget(self.followup_response, 2)
        
        self.followup_frame.layout.addLayout(self.followup_layout)
        self.followup_frame.hide()
        self.process_layout.addWidget(self.followup_frame)

    def show_process_content(self):
        """Show the process document content"""
        # Update KB combo in case KBs were added
        self.kb_combo.clear()
        kb_list = self.llm_processor.get_kb_list()
        self.kb_combo.addItems(kb_list)
        
        # Hide PDF management if visible
        if self.pdf_management_content.isVisible():
            self.pdf_management_content.hide()
            self.pdf_mgmt_btn.setStyleSheet("background-color: #8e44ad;")
        
        # Hide current active content
        if self.active_content and self.active_content != self.process_content:
            self.active_content.hide()
        
        # Show process content
        self.process_content.show()
        self.active_content = self.process_content
        
        # Update button style
        self.process_btn.setStyleSheet("background-color: #0078d4;")
        
    def load_excel(self):
        """Load data from Excel file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        
        if not file_path:
            return
            
        try:
            self.excel_data = pd.read_excel(file_path)
            self.file_path_label.setText(file_path)
            
            # Display success message
            QMessageBox.information(
                self, "Success", f"Loaded Excel with {len(self.excel_data)} rows"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load Excel file: {str(e)}"
            )
            self.excel_data = None

    def process_data(self):
        """Process data using LLM"""
        if self.excel_data is None:
            QMessageBox.warning(self, "Warning", "Please load an Excel file first")
            return
            
        selected_kb = self.kb_combo.currentText()
        if not selected_kb:
            QMessageBox.warning(self, "Warning", "Please select a knowledge base")
            return
            
        # Clear previous results
        self.clear_layout(self.results_layout)
        self.followup_frame.hide()
        
        # Display loading indicator
        loading_label = QLabel("Processing... Please wait.")
        self.results_layout.addWidget(loading_label)
        
        # Create worker for background processing
        worker = LLMWorker(self.llm_processor, self.excel_data, selected_kb)
        worker.signals.result.connect(self.handle_processing_results)
        worker.signals.error.connect(self.handle_processing_error)
        
        # Execute
        self.threadpool.start(worker)

    def handle_processing_results(self, results):
        """Handle results from LLM processing"""
        # Store results
        self.current_results = results
        
        # Clear loading indicator
        self.clear_layout(self.results_layout)
        
        # Create table model for results
        table_model = ResultsTableModel(results)
        
        # Create table view
        table_view = QTableView()
        table_view.setModel(table_model)
        table_view.setSortingEnabled(True)
        table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_view.clicked.connect(self.handle_table_click)
        
        # Add to results layout
        self.results_layout.addWidget(table_view)

    def handle_processing_error(self, error_message):
        """Handle errors from LLM processing"""
        self.clear_layout(self.results_layout)
        error_label = QLabel(f"Error: {error_message}")
        error_label.setStyleSheet("color: red;")
        self.results_layout.addWidget(error_label)

    def handle_table_click(self, index):
        """Handle clicks on the results table"""
        row = index.row()
        self.selected_row_index = row
        
        if row < 0 or row >= len(self.current_results):
            return
            
        result = self.current_results[row]
        file_path = result.get("file_path", "")
        conversation_id = result.get("conversation_id", "")
        
        # Store conversation ID for follow-ups
        self.current_conversation_id = conversation_id
        
        # Show follow-up section
        self.followup_frame.show()
        
        # Clear previous follow-up response
        self.followup_response.clear()
        
        # Load PDF if available
        if file_path and os.path.exists(file_path):
            self.load_pdf_document(file_path)
        else:
            # Clear PDF view
            self.pdf_document.close()

    def load_pdf_document(self, file_path, page=None):
        """Load a PDF document into the viewer"""
        self.pdf_document.close()
        self.pdf_document.load(file_path)
        
        if page is not None and page < self.pdf_document.pageCount():
            self.pdf_view.setPageNumber(page)

    def send_followup(self):
        """Send a follow-up question"""
        question = self.followup_input.text().strip()
        if not question:
            return
            
        if not self.current_conversation_id:
            QMessageBox.warning(self, "Warning", "Please select a result first")
            return
            
        # Clear previous response and show loading
        self.followup_response.setText("Processing follow-up question...")
        
        # Create worker for follow-up
        worker = FollowUpWorker(self.llm_processor, question, self.current_conversation_id)
        worker.signals.result.connect(self.handle_followup_result)
        worker.signals.error.connect(self.handle_followup_error)
        
        # Execute
        self.threadpool.start(worker)
        
        # Clear input
        self.followup_input.clear()

    def handle_followup_result(self, result):
        """Handle result from follow-up query"""
        answer = result.get("answer", "No answer provided")
        self.followup_response.setText(answer)
        
        # If page reference is returned, jump to that page
        page = result.get("page")
        if page is not None and self.pdf_document.status() == QPdfDocument.Status.Ready:
            self.load_pdf_document(self.pdf_document.fileName(), page)

    def handle_followup_error(self, error_message):
        """Handle error from follow-up query"""
        self.followup_response.setText(f"Error: {error_message}")

    def clear_layout(self, layout):
        """Clear all items from a layout"""
        if layout is None:
            return
            
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self.clear_layout(item.layout())
                item.layout().deleteLater()


# Main application entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show the main window
    main_window = DocumentProcessorApp()
    main_window.show()
    
    sys.exit(app.exec())
