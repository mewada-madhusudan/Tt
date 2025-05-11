import os
import sys
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
import concurrent.futures
from tqdm import tqdm

# Import PDFProcessor from the convert_to_pdf module
sys.path.append("Fixes")  # Adjust path as needed
from convert_to_pdf import PDFProcessor


class PDFConversionSignals(QObject):
    """
    Signals for PDF conversion process
    """
    started = pyqtSignal(int)  # document_id
    progress = pyqtSignal(int, float)  # document_id, progress (0-100)
    page_processed = pyqtSignal(int, int, int)  # document_id, current_page, total_pages
    completed = pyqtSignal(int, str, int)  # document_id, output_path, page_count
    error = pyqtSignal(int, str)  # document_id, error_message


class PDFConversionWorker(QRunnable):
    """
    Worker for handling PDF conversion in background thread
    """
    def __init__(self, doc_id, file_path, output_dir, use_llm=False):
        super().__init__()
        self.doc_id = doc_id
        self.file_path = file_path
        self.output_dir = output_dir
        self.use_llm = use_llm
        self.signals = PDFConversionSignals()
    
    @pyqtSlot()
    def run(self):
        """Execute the PDF conversion process"""
        try:
            self.signals.started.emit(self.doc_id)
            
            # Ensure output directory exists
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            
            # Create a custom PDFProcessor subclass that tracks progress
            class TrackedPDFProcessor(PDFProcessor):
                def __init__(self, output_dir, worker):
                    super().__init__(output_dir=output_dir)
                    self.worker = worker
                    self.total_pages = 0
                    self.processed_pages = 0
                
                def convert_pdf_to_images(self, pdf_path, dpi=300):
                    # First, call the original method to get images
                    images = super().convert_pdf_to_images(pdf_path, dpi)
                    self.total_pages = len(images)
                    # Emit signal with total pages information
                    self.worker.signals.page_processed.emit(
                        self.worker.doc_id, 0, self.total_pages
                    )
                    return images
                
                def process_page(self, args):
                    # Call the original method
                    result = super().process_page(args)
                    
                    # Increment processed pages counter and update progress
                    self.processed_pages += 1
                    progress = (self.processed_pages / self.total_pages) * 95 if self.total_pages > 0 else 0
                    
                    # Emit signals with progress information
                    self.worker.signals.progress.emit(self.worker.doc_id, progress)
                    self.worker.signals.page_processed.emit(
                        self.worker.doc_id, self.processed_pages, self.total_pages
                    )
                    
                    return result
                
                def create_editable_pdf(self, texts, output_path):
                    # Signal that we're creating the final PDF
                    self.worker.signals.progress.emit(self.worker.doc_id, 95)
                    
                    # Call the original method
                    result = super().create_editable_pdf(texts, output_path)
                    
                    # Signal progress at 99% (almost done)
                    self.worker.signals.progress.emit(self.worker.doc_id, 99)
                    
                    return result
            
            # Initialize our tracked PDF processor
            processor = TrackedPDFProcessor(output_dir=self.output_dir, worker=self)
            
            # Process the PDF - this will call all the necessary methods internally
            # and our overridden methods will track and emit progress
            output_path = processor.process_pdf(self.file_path, use_llm=self.use_llm)
            
            # Verify the output file exists
            if not os.path.exists(output_path):
                raise FileNotFoundError(f"Output file was not created: {output_path}")
            
            # Signal 100% completion
            self.signals.progress.emit(self.doc_id, 100)
            
            # Signal completion with output path and total pages
            self.signals.completed.emit(self.doc_id, output_path, processor.total_pages)
            
        except Exception as e:
            self.signals.error.emit(self.doc_id, f"Conversion error: {str(e)}")


class BatchConversionWorker(QRunnable):
    """
    Worker for processing a batch of PDF conversions sequentially
    """
    def __init__(self, db_manager, output_base_dir):
        super().__init__()
        self.db_manager = db_manager
        self.output_base_dir = output_base_dir
        self.signals = PDFConversionSignals()
        self.is_running = True  # Flag to allow stopping the worker
    
    def stop(self):
        """Stop the batch processing"""
        self.is_running = False
    
    @pyqtSlot()
    def run(self):
        """Process all pending conversions"""
        # Get all pending documents
        pending_docs = self.db_manager.get_pending_conversions()
        
        for doc in pending_docs:
            if not self.is_running:
                break  # Stop if requested
                
            doc_id = doc["id"]
            file_path = doc["original_path"]
            kb_name = doc["kb_name"]
            
            # Update status to in_progress
            self.db_manager.update_document_conversion(doc_id, "in_progress", progress=0)
            
            # Create output directory for this KB
            output_dir = os.path.join(self.output_base_dir, kb_name, "converted")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            try:
                # Signal that conversion started
                self.signals.started.emit(doc_id)
                
                # Create a custom PDFProcessor subclass that tracks progress
                class TrackedPDFProcessor(PDFProcessor):
                    def __init__(self, output_dir, worker, doc_id, db_manager):
                        super().__init__(output_dir=output_dir)
                        self.worker = worker
                        self.doc_id = doc_id
                        self.db_manager = db_manager
                        self.total_pages = 0
                        self.processed_pages = 0
                    
                    def convert_pdf_to_images(self, pdf_path, dpi=300):
                        # First, call the original method to get images
                        images = super().convert_pdf_to_images(pdf_path, dpi)
                        self.total_pages = len(images)
                        # Emit signal with total pages information
                        self.worker.signals.page_processed.emit(
                            self.doc_id, 0, self.total_pages
                        )
                        return images
                    
                    def process_page(self, args):
                        # Call the original method
                        result = super().process_page(args)
                        
                        # Increment processed pages counter and update progress
                        self.processed_pages += 1
                        progress = (self.processed_pages / self.total_pages) * 95 if self.total_pages > 0 else 0
                        
                        # Emit signals with progress information
                        self.worker.signals.progress.emit(self.doc_id, progress)
                        self.worker.signals.page_processed.emit(
                            self.doc_id, self.processed_pages, self.total_pages
                        )
                        
                        # Update progress in database
                        self.db_manager.update_document_conversion(
                            self.doc_id, "in_progress", progress=progress
                        )
                        
                        return result
                    
                    def create_editable_pdf(self, texts, output_path):
                        # Signal that we're creating the final PDF
                        self.worker.signals.progress.emit(self.doc_id, 95)
                        self.db_manager.update_document_conversion(
                            self.doc_id, "in_progress", progress=95
                        )
                        
                        # Call the original method
                        result = super().create_editable_pdf(texts, output_path)
                        
                        # Signal progress at 99% (almost done)
                        self.worker.signals.progress.emit(self.doc_id, 99)
                        self.db_manager.update_document_conversion(
                            self.doc_id, "in_progress", progress=99
                        )
                        
                        return result
                
                # Initialize our tracked PDF processor
                processor = TrackedPDFProcessor(
                    output_dir=output_dir, 
                    worker=self, 
                    doc_id=doc_id,
                    db_manager=self.db_manager
                )
                
                # Process the PDF
                output_path = processor.process_pdf(file_path, use_llm=False)
                
                # Verify the output file exists
                if not os.path.exists(output_path):
                    raise FileNotFoundError(f"Output file was not created: {output_path}")
                
                # Update database with completed status
                self.db_manager.update_document_conversion(
                    doc_id, "completed", progress=100,
                    converted_path=output_path, page_count=processor.total_pages
                )
                
                # Signal 100% completion
                self.signals.progress.emit(doc_id, 100)
                
                # Signal completion
                self.signals.completed.emit(doc_id, output_path, processor.total_pages)
                
            except Exception as e:
                error_msg = f"Conversion error: {str(e)}"
                self.db_manager.update_document_conversion(doc_id, "failed", progress=0)
                self.signals.error.emit(doc_id, error_msg)
