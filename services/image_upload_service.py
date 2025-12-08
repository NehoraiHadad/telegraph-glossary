"""Image upload service for Telegraph.

This service handles image uploads to Telegraph with validation,
temporary file management, and support for Streamlit file uploads.
"""

import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image
from telegraph import Telegraph


class ImageUploadError(Exception):
    """Custom exception for image upload errors."""

    pass


class ImageUploadService:
    """Service for uploading images to Telegraph.

    Supports direct byte uploads and Streamlit UploadedFile objects.
    Validates file types, sizes, and image integrity.
    """

    # Maximum file size: 5MB
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

    # Allowed image extensions
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}

    # Telegraph base URL for uploaded files
    TELEGRAPH_BASE_URL = "https://telegra.ph"

    def __init__(self, telegraph_client: Optional[Telegraph] = None):
        """Initialize the image upload service.

        Args:
            telegraph_client: Optional Telegraph client instance.
                            If not provided, a new client will be created.
        """
        self.telegraph = telegraph_client if telegraph_client else Telegraph()

    def upload_image(self, file_data: bytes, filename: str) -> str:
        """Upload an image to Telegraph from bytes.

        Args:
            file_data: Raw image file bytes
            filename: Original filename (used for extension validation)

        Returns:
            Full Telegraph URL of the uploaded image

        Raises:
            ImageUploadError: If validation fails or upload fails
        """
        # Validate the image
        is_valid, error_msg = self.validate_image(file_data, filename)
        if not is_valid:
            raise ImageUploadError(error_msg)

        # Create temporary file for upload
        temp_file_path = None
        try:
            # Extract file extension
            ext = Path(filename).suffix.lower()
            if not ext:
                ext = ".jpg"  # Default fallback

            # Create temporary file with proper extension
            with tempfile.NamedTemporaryFile(
                mode='wb',
                suffix=ext,
                delete=False
            ) as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name

            # Upload to Telegraph
            result = self.telegraph.upload_file(temp_file_path)

            # Parse the result
            if not result or not isinstance(result, list) or len(result) == 0:
                raise ImageUploadError("Telegraph API returned empty response")

            # Extract the file path from response
            file_info = result[0]
            if not isinstance(file_info, dict) or "src" not in file_info:
                raise ImageUploadError(
                    f"Unexpected Telegraph API response format: {result}"
                )

            # Build full URL
            file_path = file_info["src"]
            full_url = f"{self.TELEGRAPH_BASE_URL}{file_path}"

            return full_url

        except ImageUploadError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            raise ImageUploadError(
                f"Failed to upload image to Telegraph: {str(e)}"
            ) from e
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass  # Best effort cleanup

    def upload_from_streamlit(self, uploaded_file) -> str:
        """Upload an image from a Streamlit UploadedFile object.

        Args:
            uploaded_file: Streamlit UploadedFile object from st.file_uploader

        Returns:
            Full Telegraph URL of the uploaded image

        Raises:
            ImageUploadError: If validation fails or upload fails
        """
        try:
            # Read file data
            file_data = uploaded_file.read()
            filename = uploaded_file.name

            # Upload using the main method
            return self.upload_image(file_data, filename)

        except ImageUploadError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            raise ImageUploadError(
                f"Failed to process Streamlit uploaded file: {str(e)}"
            ) from e

    def upload_multiple(
        self,
        files: List[Tuple[bytes, str]]
    ) -> List[Tuple[str, Optional[str]]]:
        """Upload multiple images to Telegraph.

        Args:
            files: List of (file_data, filename) tuples

        Returns:
            List of (filename, url_or_error) tuples.
            If upload succeeds, url_or_error is the Telegraph URL.
            If upload fails, url_or_error is None and error is logged.
        """
        results = []

        for file_data, filename in files:
            try:
                url = self.upload_image(file_data, filename)
                results.append((filename, url))
            except ImageUploadError as e:
                # Log error but continue with other files
                results.append((filename, None))
                # Could add logging here if needed

        return results

    @staticmethod
    def validate_image(file_data: bytes, filename: str) -> Tuple[bool, str]:
        """Validate an image file.

        Checks:
        1. File extension is allowed
        2. File size is within limits
        3. File is a valid image (can be opened by Pillow)

        Args:
            file_data: Raw image file bytes
            filename: Original filename

        Returns:
            Tuple of (is_valid, error_message).
            If valid: (True, "")
            If invalid: (False, "error description")
        """
        # Check file extension
        ext = Path(filename).suffix.lower()
        if ext not in ImageUploadService.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ImageUploadService.ALLOWED_EXTENSIONS))
            return False, (
                f"Invalid file type '{ext}'. "
                f"Allowed types: {allowed}"
            )

        # Check file size
        file_size = len(file_data)
        if file_size == 0:
            return False, "File is empty"

        if file_size > ImageUploadService.MAX_FILE_SIZE_BYTES:
            max_mb = ImageUploadService.MAX_FILE_SIZE_BYTES / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            return False, (
                f"File size ({actual_mb:.2f}MB) exceeds maximum "
                f"allowed size ({max_mb:.0f}MB)"
            )

        # Verify it's a valid image by attempting to open it
        try:
            img = Image.open(BytesIO(file_data))
            # Verify the image by trying to get basic info
            img.verify()

            # Additional check: make sure it's a supported format
            if img.format.lower() not in ("jpeg", "jpg", "png", "gif"):
                return False, (
                    f"Unsupported image format: {img.format}. "
                    f"Supported formats: JPEG, PNG, GIF"
                )

        except Exception as e:
            return False, f"Invalid or corrupted image file: {str(e)}"

        # All checks passed
        return True, ""

    @staticmethod
    def get_image_info(file_data: bytes) -> Optional[dict]:
        """Get information about an image file.

        Args:
            file_data: Raw image file bytes

        Returns:
            Dictionary with image info (format, size, mode) or None if invalid
        """
        try:
            img = Image.open(BytesIO(file_data))
            return {
                "format": img.format,
                "size": img.size,  # (width, height)
                "mode": img.mode,  # RGB, RGBA, etc.
                "width": img.size[0],
                "height": img.size[1],
            }
        except Exception:
            return None
