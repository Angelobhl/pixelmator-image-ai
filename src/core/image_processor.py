"""
Image processing module.
Handles image preprocessing, resizing, and format conversion.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image


@dataclass
class ImagePreprocessResult:
    """Result of image preprocessing."""
    original_path: Path
    processed_path: Path
    original_size: tuple  # (width, height)
    processed_size: tuple  # (width, height)
    was_resized: bool
    format: str


class ImagePreprocessor:
    """Image preprocessor for API compatibility."""

    def __init__(self, max_size: int = 2048, quality: int = 95):
        self.max_size = max_size
        self.quality = quality

    def check_size(self, image_path: Path) -> bool:
        """Check if image size is within limits."""
        with Image.open(image_path) as img:
            width, height = img.size
            return max(width, height) <= self.max_size

    def get_size(self, image_path: Path) -> tuple:
        """Get image dimensions."""
        with Image.open(image_path) as img:
            return img.size

    def resize(
        self,
        image_path: Path,
        output_path: Optional[Path] = None,
        max_size: Optional[int] = None
    ) -> ImagePreprocessResult:
        """Resize image to fit within max_size while maintaining aspect ratio."""
        max_size = max_size or self.max_size
        output_path = output_path or image_path

        with Image.open(image_path) as img:
            original_size = img.size
            width, height = original_size

            # Check if resize is needed
            if max(width, height) <= max_size:
                was_resized = False
                processed_size = original_size
                if image_path != output_path:
                    img.save(output_path, quality=self.quality)
            else:
                was_resized = True
                # Calculate new size maintaining aspect ratio
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))

                processed_size = (new_width, new_height)
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Handle transparency for PNG
                if resized_img.mode in ('RGBA', 'LA', 'P'):
                    resized_img.save(output_path, 'PNG', quality=self.quality)
                else:
                    resized_img.save(output_path, quality=self.quality)

        return ImagePreprocessResult(
            original_path=image_path,
            processed_path=output_path,
            original_size=original_size,
            processed_size=processed_size,
            was_resized=was_resized,
            format=output_path.suffix.lstrip('.').upper()
        )

    def convert_format(
        self,
        image_path: Path,
        output_path: Path,
        format: str = "PNG"
    ) -> Path:
        """Convert image to specified format."""
        with Image.open(image_path) as img:
            # Handle transparency
            if format.upper() == "PNG" and img.mode not in ('RGBA', 'LA'):
                img = img.convert('RGBA')
            elif format.upper() == "JPEG" and img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            img.save(output_path, format, quality=self.quality)

        return output_path

    def to_base64(self, image_path: Path) -> str:
        """Convert image to base64 string."""
        import base64
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")