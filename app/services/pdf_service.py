"""PDF processing and validation service."""

import io
import tempfile
import os
from typing import Tuple
import PyPDF2
import pdfplumber
from pdf2markdown4llm import PDF2Markdown4LLM
import structlog

from app.config import settings
from app.exceptions import FileValidationError, ValidationError

logger = structlog.get_logger()


class PdfProcessingError(ValidationError):
    """Exception raised for PDF processing errors."""
    pass


class PdfService:
    """Service for PDF processing and text extraction."""
    
    def __init__(self):
        self.max_file_size = settings.max_file_size_bytes
        self.allowed_types = settings.allowed_pdf_types_list
    
    def validate_pdf_file(self, file_data: bytes, filename: str) -> Tuple[bytes, str]:
        """Validate uploaded PDF file."""
        file_size = len(file_data)
        max_size_mb = self.max_file_size // (1024 * 1024)  # Convert to MB for display
        
        # Check file size
        if file_size > self.max_file_size:
            file_size_mb = file_size / (1024 * 1024)
            raise FileValidationError(
                f"PDF file size {file_size_mb:.2f}MB exceeds maximum allowed size of {max_size_mb}MB. "
                f"Please upload a smaller PDF file."
            )
        
        # Check minimum file size (PDFs should be at least a few KB)
        min_size = 1024  # 1KB minimum
        if file_size < min_size:
            raise FileValidationError(
                f"PDF file size {file_size} bytes is too small. Please upload a valid PDF file."
            )
        
        # Extract file extension
        file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # Check file type
        if file_extension not in self.allowed_types:
            raise FileValidationError(
                f"File type '{file_extension}' not allowed. Supported types: {', '.join(self.allowed_types)}"
            )
        
        # Validate that the file is actually a PDF
        try:
            # Try to read the PDF with PyPDF2 to validate it's a proper PDF
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))
            num_pages = len(pdf_reader.pages)
            
            if num_pages == 0:
                raise PdfProcessingError("PDF file contains no pages")
            
            logger.info(
                "Successfully validated PDF file",
                filename=filename,
                file_size=len(file_data),
                num_pages=num_pages
            )
            
            return file_data, file_extension
            
        except Exception as e:
            logger.error("PDF validation failed", filename=filename, error=str(e))
            raise PdfProcessingError(f"Invalid PDF file: {str(e)}")
    
    def extract_text_from_pdf(self, pdf_data: bytes) -> str:
        """Extract text from PDF and convert to markdown format using pdf2markdown4llm."""
        try:
            # Create a temporary file to store the PDF data
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_data)
                temp_file_path = temp_file.name
            
            try:
                # Initialize PDF2Markdown4LLM converter
                def progress_callback(progress):
                    """Callback function to handle progress updates."""
                    logger.info(
                        f"PDF conversion progress: {progress.phase.value}, "
                        f"Page {progress.current_page}/{progress.total_pages}, "
                        f"Progress: {progress.percentage:.1f}%, "
                        f"Message: {progress.message}"
                    )
                
                # Configure converter with optimal settings for LLM processing
                converter = PDF2Markdown4LLM(
                    remove_headers=False,  # Keep headers for better structure
                    skip_empty_tables=True,  # Skip empty tables to reduce noise
                    table_header="### Table",  # Use consistent table headers
                    progress_callback=progress_callback
                )
                
                # Convert PDF to Markdown
                logger.info("Starting PDF to Markdown conversion using pdf2markdown4llm")
                markdown_content = converter.convert(temp_file_path)
                
                if not markdown_content or not markdown_content.strip():
                    raise PdfProcessingError("No readable text found in the PDF")
                
                logger.info(
                    "Successfully converted PDF to Markdown",
                    content_length=len(markdown_content)
                )
                
                return markdown_content
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    logger.warning(f"Failed to delete temporary file: {temp_file_path}")
            
        except Exception as e:
            logger.error("PDF to Markdown conversion failed", error=str(e))
            raise PdfProcessingError(f"Failed to convert PDF to Markdown: {str(e)}")
    


# Global service instance
pdf_service = PdfService()
