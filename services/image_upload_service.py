"""Image upload service for Telegraph.

This service handles image uploads to Telegraph with validation,
temporary file management, and support for Streamlit file uploads.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import requests


class ImageUploadError(Exception):
    """Custom exception for image upload errors."""
    pass


class ImageUploadService:
    """Service for uploading images to Telegraph.

    Supports direct byte uploads and Streamlit UploadedFile objects.
    Validates file types and sizes before upload.
    """

    # Maximum file size: 5MB
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

    # Allowed image extensions
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}

    # Telegraph upload endpoint
    TELEGRAPH_UPLOAD_URL = "https://telegra.ph/upload"
    TELEGRAPH_BASE_URL = "https://telegra.ph"

    def __init__(self, telegraph_client=None):
        """Initialize the image upload service.

        Args:
            telegraph_client: Optional Telegraph client instance (not used, kept for compatibility)
        """
        pass  # We use direct HTTP requests instead of the library

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

        # Get file extension for MIME type
        ext = Path(filename).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif"
        }
        mime_type = mime_types.get(ext, "application/octet-stream")

        # Upload directly using requests (more reliable than telegraph library)
        try:
            response = requests.post(
                self.TELEGRAPH_UPLOAD_URL,
                files={"file": (filename, file_data, mime_type)},
                timeout=30
            )

            # Check HTTP status
            if response.status_code != 200:
                raise ImageUploadError(f"Telegraph returned status {response.status_code}: {response.text[:200]}")

            # Parse response
            try:
                result = response.json()
            except ValueError:
                raise ImageUploadError(f"Invalid response from Telegraph: {response.text[:200]}")

            # Handle error response
            if isinstance(result, str):
                raise ImageUploadError(f"Telegraph error: {result}")

            if isinstance(result, dict) and "error" in result:
                raise ImageUploadError(f"Telegraph error: {result['error']}")

            # Extract file path from response
            if isinstance(result, list) and len(result) > 0:
                file_info = result[0]
                if isinstance(file_info, dict) and "src" in file_info:
                    return f"{self.TELEGRAPH_BASE_URL}{file_info['src']}"

            raise ImageUploadError(f"Unexpected Telegraph response format: {result}")

        except requests.RequestException as e:
            raise ImageUploadError(f"Network error during upload: {str(e)}") from e

    def upload_from_file_path(self, file_path: str) -> str:
        """Upload an image from a file path.

        Args:
            file_path: Path to the image file

        Returns:
            Full Telegraph URL of the uploaded image

        Raises:
            ImageUploadError: If validation fails or upload fails
        """
        if not os.path.exists(file_path):
            raise ImageUploadError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            file_data = f.read()

        filename = os.path.basename(file_path)
        return self.upload_image(file_data, filename)

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
            # Read file data - handle both seekable and non-seekable files
            uploaded_file.seek(0)
            file_data = uploaded_file.read()
            filename = uploaded_file.name

            return self.upload_image(file_data, filename)

        except ImageUploadError:
            raise
        except Exception as e:
            raise ImageUploadError(f"Failed to process uploaded file: {str(e)}") from e

    @staticmethod
    def validate_image(file_data: bytes, filename: str) -> Tuple[bool, str]:
        """Validate an image file.

        Checks:
        1. File extension is allowed
        2. File size is within limits

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
            return False, f"Invalid file type '{ext}'. Allowed: {allowed}"

        # Check file size
        file_size = len(file_data)
        if file_size == 0:
            return False, "File is empty"

        if file_size > ImageUploadService.MAX_FILE_SIZE_BYTES:
            max_mb = ImageUploadService.MAX_FILE_SIZE_BYTES / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            return False, f"File too large ({actual_mb:.1f}MB). Maximum: {max_mb:.0f}MB"

        return True, ""
