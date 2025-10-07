"""PDF processing and validation service."""

import io
from typing import Tuple
import PyPDF2
import pdfplumber
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
        """Extract text from PDF and convert to markdown format."""
        try:
            markdown_content = []
            
            # Use pdfplumber for better text extraction
            with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    logger.info(f"Processing page {page_num} of {len(pdf.pages)}")
                    
                    # Extract text from the page
                    page_text = page.extract_text()
                    
                    if page_text:
                        # Clean up the text
                        cleaned_text = self._clean_text(page_text)
                        
                        # Add page header
                        if len(pdf.pages) > 1:
                            markdown_content.append(f"## Page {page_num}\n")
                        
                        # Add the text content
                        markdown_content.append(cleaned_text)
                        
                        # Add spacing between pages
                        if page_num < len(pdf.pages):
                            markdown_content.append("\n---\n")
                    else:
                        logger.warning(f"No text found on page {page_num}")
                        if len(pdf.pages) > 1:
                            markdown_content.append(f"## Page {page_num}\n")
                            markdown_content.append("*[No readable text found on this page]*\n")
            
            # Join all content
            full_content = "\n".join(markdown_content)
            
            if not full_content.strip():
                raise PdfProcessingError("No readable text found in the PDF")
            
            logger.info(
                "Successfully extracted text from PDF",
                total_pages=len(pdf.pages),
                content_length=len(full_content)
            )
            
            return full_content
            
        except Exception as e:
            logger.error("PDF text extraction failed", error=str(e))
            raise PdfProcessingError(f"Failed to extract text from PDF: {str(e)}")
    
    def _clean_text(self, text: str) -> str:
        """Clean and format extracted text."""
        if not text:
            return ""
        
        # Remove excessive whitespace
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Strip whitespace from each line
            cleaned_line = line.strip()
            
            # Skip empty lines
            if not cleaned_line:
                continue
            
            # Add proper markdown formatting for headers (lines that are all caps or start with numbers)
            if cleaned_line.isupper() and len(cleaned_line) > 3:
                cleaned_lines.append(f"### {cleaned_line}")
            elif cleaned_line and cleaned_line[0].isdigit() and '.' in cleaned_line:
                cleaned_lines.append(f"**{cleaned_line}**")
            else:
                cleaned_lines.append(cleaned_line)
        
        # Join lines with proper spacing
        return "\n\n".join(cleaned_lines)


# Global service instance
pdf_service = PdfService()
