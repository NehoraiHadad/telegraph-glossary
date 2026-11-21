"""imgbb image hosting service for Telegraph Glossary.

This service handles image uploads to imgbb.com, which provides free
image hosting with a simple API. Images uploaded here can be used
in Telegraph pages.

To get an API key: https://api.imgbb.com/ (free, requires signup)
"""

import base64
import requests
from typing import Optional, Tuple


class ImgbbUploadError(Exception):
    """Exception raised when image upload to imgbb fails."""
    pass


class ImgbbService:
    """Service for uploading images to imgbb.com.

    imgbb provides free image hosting with permanent storage.
    API documentation: https://api.imgbb.com/
    """

    UPLOAD_URL = "https://api.imgbb.com/1/upload"

    # Supported image formats
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

    # Maximum file size (32MB for imgbb)
    MAX_FILE_SIZE_BYTES = 32 * 1024 * 1024

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the imgbb service.

        Args:
            api_key: imgbb API key. Get one free at https://api.imgbb.com/
        """
        self.api_key = api_key

    def set_api_key(self, api_key: str) -> None:
        """Set the API key.

        Args:
            api_key: imgbb API key
        """
        self.api_key = api_key

    def is_configured(self) -> bool:
        """Check if the service is configured with an API key.

        Returns:
            True if API key is set
        """
        return bool(self.api_key)

    def upload_image(self, file_data: bytes, filename: str) -> str:
        """Upload an image to imgbb.

        Args:
            file_data: Raw image bytes
            filename: Original filename (used for validation)

        Returns:
            Direct URL to the uploaded image

        Raises:
            ImgbbUploadError: If upload fails
        """
        if not self.api_key:
            raise ImgbbUploadError(
                "imgbb API key not configured. "
                "Get a free key at https://api.imgbb.com/"
            )

        # Validate the image
        is_valid, error = self.validate_image(file_data, filename)
        if not is_valid:
            raise ImgbbUploadError(error)

        # Convert to base64
        image_base64 = base64.b64encode(file_data).decode('utf-8')

        # Upload to imgbb
        try:
            response = requests.post(
                self.UPLOAD_URL,
                data={
                    "key": self.api_key,
                    "image": image_base64,
                    "name": filename.rsplit('.', 1)[0] if '.' in filename else filename,
                },
                timeout=60  # Longer timeout for large images
            )

            # Check HTTP status
            if response.status_code != 200:
                raise ImgbbUploadError(
                    f"imgbb returned status {response.status_code}: {response.text[:200]}"
                )

            # Parse response
            result = response.json()

            if not result.get("success"):
                error_msg = result.get("error", {}).get("message", "Unknown error")
                raise ImgbbUploadError(f"imgbb error: {error_msg}")

            # Get the direct image URL
            image_url = result.get("data", {}).get("url")
            if not image_url:
                # Fallback to display_url
                image_url = result.get("data", {}).get("display_url")

            if not image_url:
                raise ImgbbUploadError("No image URL in imgbb response")

            return image_url

        except requests.RequestException as e:
            raise ImgbbUploadError(f"Network error: {str(e)}") from e
        except ValueError as e:
            raise ImgbbUploadError(f"Invalid response from imgbb: {str(e)}") from e

    def upload_from_streamlit(self, uploaded_file) -> str:
        """Upload an image from Streamlit's file_uploader.

        Args:
            uploaded_file: Streamlit UploadedFile object

        Returns:
            Direct URL to the uploaded image

        Raises:
            ImgbbUploadError: If upload fails
        """
        try:
            uploaded_file.seek(0)
            file_data = uploaded_file.read()
            filename = uploaded_file.name
            return self.upload_image(file_data, filename)
        except ImgbbUploadError:
            raise
        except Exception as e:
            raise ImgbbUploadError(f"Failed to process file: {str(e)}") from e

    def validate_image(self, file_data: bytes, filename: str) -> Tuple[bool, str]:
        """Validate an image file.

        Args:
            file_data: Raw image bytes
            filename: Original filename

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check filename
        if not filename:
            return False, "Filename is required"

        # Check extension
        ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
            return False, f"Invalid file type '{ext}'. Allowed: {allowed}"

        # Check file size
        if len(file_data) == 0:
            return False, "File is empty"

        if len(file_data) > self.MAX_FILE_SIZE_BYTES:
            max_mb = self.MAX_FILE_SIZE_BYTES / (1024 * 1024)
            actual_mb = len(file_data) / (1024 * 1024)
            return False, f"File too large ({actual_mb:.1f}MB). Maximum: {max_mb:.0f}MB"

        return True, ""

    @staticmethod
    def get_setup_instructions() -> str:
        """Get instructions for setting up imgbb API.

        Returns:
            Setup instructions string
        """
        return """
## Setup imgbb Image Hosting

1. Go to https://api.imgbb.com/
2. Click "Get API Key" and sign up (free)
3. Copy your API key
4. Paste it in Settings → Image Hosting → imgbb API Key

Your images will be hosted permanently on imgbb.com for free.
"""
