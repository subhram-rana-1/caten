"""Image processing and validation service."""

import io
from typing import Tuple
from PIL import Image, ImageOps
import structlog

from app.config import settings
from app.exceptions import FileValidationError, ImageProcessingError

logger = structlog.get_logger()


class ImageService:
    """Service for image processing and validation."""
    
    def __init__(self):
        self.max_file_size = settings.max_file_size_bytes
        self.allowed_types = settings.allowed_image_types_list
    
    def validate_image_file(self, file_data: bytes, filename: str) -> Tuple[bytes, str]:
        """Validate uploaded image file."""
        # Check file size
        if len(file_data) > self.max_file_size:
            raise FileValidationError(
                f"File size {len(file_data)} bytes exceeds maximum allowed size of {self.max_file_size} bytes"
            )
        
        # Extract file extension
        file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # Check file type
        if file_extension not in self.allowed_types:
            raise FileValidationError(
                f"File type '{file_extension}' not allowed. Supported types: {', '.join(self.allowed_types)}"
            )
        
        # Validate that the file is actually an image
        try:
            image = Image.open(io.BytesIO(file_data))
            image.verify()  # Verify that it's a valid image
            
            # Re-open the image since verify() closes it
            image = Image.open(io.BytesIO(file_data))
            
            # Convert to RGB if necessary (for HEIC and other formats)
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            
            # Auto-rotate based on EXIF data
            image = ImageOps.exif_transpose(image)
            
            # Save processed image back to bytes
            processed_image_io = io.BytesIO()
            image_format = 'JPEG' if file_extension in ['jpg', 'jpeg', 'heic'] else 'PNG'
            image.save(processed_image_io, format=image_format, quality=95)
            processed_image_data = processed_image_io.getvalue()
            
            logger.info(
                "Successfully validated and processed image",
                filename=filename,
                original_size=len(file_data),
                processed_size=len(processed_image_data),
                format=image_format,
                dimensions=f"{image.width}x{image.height}"
            )
            
            return processed_image_data, image_format.lower()
            
        except Exception as e:
            logger.error("Image validation failed", filename=filename, error=str(e))
            raise ImageProcessingError(f"Invalid image file: {str(e)}")
    
    def preprocess_image_for_ocr(self, image_data: bytes) -> bytes:
        """Preprocess image for better OCR results."""
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to grayscale for better OCR
            if image.mode != 'L':
                image = image.convert('L')
            
            # Enhance contrast
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # Resize if too small (minimum 300px on smallest side)
            width, height = image.size
            min_dimension = min(width, height)
            if min_dimension < 300:
                scale_factor = 300 / min_dimension
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save processed image
            processed_io = io.BytesIO()
            image.save(processed_io, format='PNG')
            processed_data = processed_io.getvalue()
            
            logger.info("Successfully preprocessed image for OCR", 
                       original_size=len(image_data), 
                       processed_size=len(processed_data))
            
            return processed_data
            
        except Exception as e:
            logger.error("Image preprocessing failed", error=str(e))
            raise ImageProcessingError(f"Failed to preprocess image: {str(e)}")


# Global service instance
image_service = ImageService()
