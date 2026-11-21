"""Image URL validation service for Telegraph.

Note: Telegraph has disabled direct image uploads.
Users must host images on external services (imgbb, imgur, postimages, etc.)
and use the image URL in their content.

This service provides URL validation utilities.
"""

import re
from typing import Tuple
from urllib.parse import urlparse


class ImageUploadError(Exception):
    """Custom exception for image-related errors."""
    pass


class ImageUploadService:
    """Service for validating image URLs for Telegraph.

    Note: Direct upload to Telegraph is no longer supported.
    This service now focuses on URL validation.
    """

    # Allowed image extensions
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    # Known image hosting services (for reference)
    KNOWN_IMAGE_HOSTS = [
        "i.ibb.co",
        "i.imgur.com",
        "imgur.com",
        "postimg.cc",
        "i.postimg.cc",
        "telegra.ph",
        "upload.wikimedia.org",
    ]

    def __init__(self, telegraph_client=None):
        """Initialize the service.

        Args:
            telegraph_client: Ignored - kept for backward compatibility
        """
        pass

    @staticmethod
    def validate_image_url(url: str) -> Tuple[bool, str]:
        """Validate an image URL.

        Checks:
        1. URL format is valid
        2. URL uses http or https
        3. URL looks like an image (optional - some hosts don't include extension)

        Args:
            url: The URL to validate

        Returns:
            Tuple of (is_valid, error_message).
            If valid: (True, "")
            If invalid: (False, "error description")
        """
        if not url:
            return False, "URL is empty"

        url = url.strip()

        # Check URL format
        try:
            parsed = urlparse(url)
        except Exception:
            return False, "Invalid URL format"

        # Must have scheme and netloc
        if not parsed.scheme:
            return False, "URL must start with http:// or https://"

        if parsed.scheme not in ('http', 'https'):
            return False, "URL must use http or https protocol"

        if not parsed.netloc:
            return False, "Invalid URL - no domain found"

        return True, ""

    @staticmethod
    def is_likely_image_url(url: str) -> bool:
        """Check if a URL is likely pointing to an image.

        This is a heuristic check - not all image URLs have extensions.

        Args:
            url: The URL to check

        Returns:
            True if the URL likely points to an image
        """
        if not url:
            return False

        url_lower = url.lower()

        # Check for common image extensions
        for ext in ImageUploadService.ALLOWED_EXTENSIONS:
            if ext in url_lower:
                return True

        # Check for known image hosting services
        for host in ImageUploadService.KNOWN_IMAGE_HOSTS:
            if host in url_lower:
                return True

        return False

    @staticmethod
    def get_image_hosting_tips() -> str:
        """Return tips for hosting images.

        Returns:
            String with tips for users
        """
        return """
To add images to your Telegraph page:

1. Upload your image to a free hosting service:
   - imgbb.com (no signup required)
   - imgur.com
   - postimages.org

2. Copy the direct image URL (should end in .jpg, .png, etc.)

3. Paste the URL in the image field or use markdown:
   ![description](your_image_url)

Note: Telegraph no longer supports direct image uploads.
"""

    # Legacy methods - kept for backward compatibility but deprecated

    def upload_image(self, file_data: bytes, filename: str) -> str:
        """DEPRECATED: Telegraph has disabled direct uploads.

        Raises:
            ImageUploadError: Always raises - direct upload not supported
        """
        raise ImageUploadError(
            "Telegraph has disabled direct image uploads. "
            "Please upload your image to imgbb.com, imgur.com, or another "
            "image hosting service and use the URL instead."
        )

    def upload_from_file_path(self, file_path: str) -> str:
        """DEPRECATED: Telegraph has disabled direct uploads.

        Raises:
            ImageUploadError: Always raises - direct upload not supported
        """
        raise ImageUploadError(
            "Telegraph has disabled direct image uploads. "
            "Please upload your image to an external hosting service."
        )

    def upload_from_streamlit(self, uploaded_file) -> str:
        """DEPRECATED: Telegraph has disabled direct uploads.

        Raises:
            ImageUploadError: Always raises - direct upload not supported
        """
        raise ImageUploadError(
            "Telegraph has disabled direct image uploads. "
            "Please upload your image to an external hosting service."
        )

    @staticmethod
    def validate_image(file_data: bytes, filename: str) -> Tuple[bool, str]:
        """DEPRECATED: Kept for backward compatibility.

        Args:
            file_data: Ignored
            filename: Filename to check extension

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not filename:
            return False, "Filename is required"

        ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ImageUploadService.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ImageUploadService.ALLOWED_EXTENSIONS))
            return False, f"Invalid file type '{ext}'. Allowed: {allowed}"

        return True, ""
