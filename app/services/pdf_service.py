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
        """Extract text from PDF and convert to markdown format with bold text preservation."""
        try:
            # Create a temporary file to store the PDF data
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_data)
                temp_file_path = temp_file.name
            
            try:
                # First try pdf2markdown4llm for structure preservation
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
                
                # Now enhance with bold text detection and indentation using pdfplumber
                logger.info("Enhancing markdown with bold text formatting and indentation")
                enhanced_content = self._enhance_with_formatting(temp_file_path, markdown_content)
                
                logger.info(
                    "Successfully converted PDF to Markdown with bold formatting",
                    content_length=len(enhanced_content)
                )
                
                return enhanced_content
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    logger.warning(f"Failed to delete temporary file: {temp_file_path}")
            
        except Exception as e:
            logger.error("PDF to Markdown conversion failed", error=str(e))
            raise PdfProcessingError(f"Failed to convert PDF to Markdown: {str(e)}")
    
    def _enhance_with_formatting(self, pdf_path: str, markdown_content: str) -> str:
        """Enhance markdown content with bold text formatting and proper indentation."""
        try:
            import re
            
            # Extract text with formatting information using pdfplumber
            bold_texts = []
            indentation_info = []
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract text objects with font information
                    text_objects = page.chars
                    
                    # Group characters by font weight to identify bold text
                    current_text = ""
                    current_font_weight = None
                    current_x = None
                    
                    for char in text_objects:
                        font_name = char.get('fontname', '').lower()
                        font_size = char.get('size', 0)
                        text = char.get('text', '')
                        x0 = char.get('x0', 0)
                        
                        # Detect bold fonts (common patterns)
                        is_bold = any(keyword in font_name for keyword in [
                            'bold', 'black', 'heavy', 'demibold', 'semibold'
                        ]) or font_name.endswith('-b') or font_name.endswith('bold')
                        
                        # If font weight changed, process the previous text
                        if current_font_weight is not None and current_font_weight != is_bold:
                            if current_font_weight and current_text.strip():
                                bold_texts.append(current_text.strip())
                            current_text = ""
                        
                        current_font_weight = is_bold
                        current_text += text
                        
                        # Track indentation for bullet points and multi-line text
                        if text.strip() and current_x is None:
                            current_x = x0
                        elif text == '\n' or text == ' ':
                            # Reset x position tracking for new lines
                            if text == '\n':
                                current_x = None
                    
                    # Process the last text segment
                    if current_font_weight and current_text.strip():
                        bold_texts.append(current_text.strip())
                    
                    # Extract indentation patterns from text objects
                    self._extract_indentation_patterns(page, indentation_info)
            
            # Remove duplicates and sort by length (longest first) to avoid partial replacements
            bold_texts = list(set(bold_texts))
            bold_texts.sort(key=len, reverse=True)
            
            # Apply bold formatting to markdown content
            enhanced_content = markdown_content
            
            for bold_text in bold_texts:
                if bold_text and len(bold_text) > 1:  # Skip single characters
                    # Escape special regex characters
                    escaped_text = re.escape(bold_text)
                    # Replace with markdown bold formatting, but avoid double-wrapping
                    pattern = f'(?<!\\*\\*){escaped_text}(?!\\*\\*)'
                    replacement = f'**{bold_text}**'
                    enhanced_content = re.sub(pattern, replacement, enhanced_content)
            
            # Apply indentation fixes
            enhanced_content = self._fix_indentation(enhanced_content)
            
            logger.info(f"Enhanced markdown with {len(bold_texts)} bold text segments and indentation fixes")
            return enhanced_content
            
        except Exception as e:
            logger.warning(f"Failed to enhance with formatting: {str(e)}")
            # Return original content if enhancement fails
            return markdown_content
    
    def _extract_indentation_patterns(self, page, indentation_info):
        """Extract indentation patterns from page text objects."""
        try:
            # Get text objects sorted by y position (top to bottom)
            chars = sorted(page.chars, key=lambda x: (-x['top'], x['x0']))
            
            current_line_x = None
            current_line_text = ""
            bullet_patterns = []
            
            for char in chars:
                text = char.get('text', '')
                x0 = char.get('x0', 0)
                
                if text == '\n':
                    if current_line_text.strip():
                        # Check if this line starts with a bullet point
                        if any(current_line_text.strip().startswith(bullet) for bullet in ['●', '•', '▪', '-', '*']):
                            bullet_patterns.append({
                                'text': current_line_text.strip(),
                                'x0': current_line_x,
                                'indent_level': self._calculate_indent_level(current_line_x, bullet_patterns)
                            })
                    current_line_x = None
                    current_line_text = ""
                else:
                    if current_line_x is None:
                        current_line_x = x0
                    current_line_text += text
            
            # Process the last line
            if current_line_text.strip():
                if any(current_line_text.strip().startswith(bullet) for bullet in ['●', '•', '▪', '-', '*']):
                    bullet_patterns.append({
                        'text': current_line_text.strip(),
                        'x0': current_line_x,
                        'indent_level': self._calculate_indent_level(current_line_x, bullet_patterns)
                    })
            
            indentation_info.extend(bullet_patterns)
            
        except Exception as e:
            logger.warning(f"Failed to extract indentation patterns: {str(e)}")
    
    def _calculate_indent_level(self, x0, existing_patterns):
        """Calculate indentation level based on x position."""
        if not existing_patterns:
            return 0
        
        # Find the closest x position to determine indentation level
        x_positions = sorted([p['x0'] for p in existing_patterns])
        
        for i, x_pos in enumerate(x_positions):
            if abs(x0 - x_pos) < 10:  # Within 10 points, consider same level
                return i
        
        return len(x_positions)  # New indentation level
    
    def _fix_indentation(self, content: str) -> str:
        """Fix indentation issues in markdown content."""
        import re
        
        lines = content.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Handle bullet points with proper indentation
            if re.match(r'^[●•▪\-\*]\s+', line.strip()):
                # This is a bullet point
                bullet_match = re.match(r'^([●•▪\-\*])\s+(.+)', line.strip())
                if bullet_match:
                    bullet_char = bullet_match.group(1)
                    bullet_text = bullet_match.group(2)
                    
                    # Check if this is a multi-line bullet point
                    if len(bullet_text) > 50:  # Likely to wrap
                        # Split long text and add proper hanging indent
                        words = bullet_text.split()
                        if len(words) > 8:  # Split into multiple lines
                            first_line = f"{bullet_char} {' '.join(words[:8])}"
                            remaining_words = words[8:]
                            
                            # Create hanging indent for continuation lines
                            indent_spaces = " " * (len(bullet_char) + 1)  # Space after bullet
                            continuation_lines = []
                            
                            # Split remaining words into chunks
                            for i in range(0, len(remaining_words), 8):
                                chunk = remaining_words[i:i+8]
                                continuation_lines.append(f"{indent_spaces}{' '.join(chunk)}")
                            
                            fixed_lines.append(first_line)
                            fixed_lines.extend(continuation_lines)
                        else:
                            fixed_lines.append(line.strip())
                    else:
                        fixed_lines.append(line.strip())
                else:
                    fixed_lines.append(line.strip())
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    


# Global service instance
pdf_service = PdfService()
