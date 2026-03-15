"""
Configuration management module.
Handles application settings using environment variables.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class AppConfig:
    """Application configuration."""
    # API Configuration
    api_key: str = ""
    default_model: str = "google/gemini-3-pro-image-preview"
    temperature: float = 0.7
    max_tokens: int = 4096

    # Image Processing Configuration
    max_image_size: int = 2048
    image_quality: int = 95

    # UI Configuration
    window_opacity: float = 0.9
    auto_hide: bool = True
    show_notification: bool = True
    play_sound: bool = False

    # Paths (relative to project root)
    temp_dir: str = "./temp"
    cache_dir: str = "./cache"

    # Debug mode
    debug_mode: bool = False


class ConfigManager:
    """Configuration manager for loading settings from environment variables."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config: AppConfig = AppConfig()
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Load .env file if it exists
        env_path = self.project_root / ".env"
        load_dotenv(env_path)

        # Load each configuration from environment variables
        # API Configuration
        self.config.api_key = os.getenv("GEMINI_BRIDGE_API_KEY", self.config.api_key)
        self.config.default_model = os.getenv("GEMINI_BRIDGE_DEFAULT_MODEL", self.config.default_model)
        self.config.temperature = float(os.getenv("GEMINI_BRIDGE_TEMPERATURE", str(self.config.temperature)))
        self.config.max_tokens = int(os.getenv("GEMINI_BRIDGE_MAX_TOKENS", str(self.config.max_tokens)))

        # Image Processing Configuration
        self.config.max_image_size = int(os.getenv("GEMINI_BRIDGE_MAX_IMAGE_SIZE", str(self.config.max_image_size)))
        self.config.image_quality = int(os.getenv("GEMINI_BRIDGE_IMAGE_QUALITY", str(self.config.image_quality)))

        # UI Configuration
        self.config.window_opacity = float(os.getenv("GEMINI_BRIDGE_WINDOW_OPACITY", str(self.config.window_opacity)))
        self.config.auto_hide = self._parse_bool(os.getenv("GEMINI_BRIDGE_AUTO_HIDE", str(self.config.auto_hide)))
        self.config.show_notification = self._parse_bool(os.getenv("GEMINI_BRIDGE_SHOW_NOTIFICATION", str(self.config.show_notification)))
        self.config.play_sound = self._parse_bool(os.getenv("GEMINI_BRIDGE_PLAY_SOUND", str(self.config.play_sound)))

        # Debug Mode
        self.config.debug_mode = self._parse_bool(os.getenv("GEMINI_BRIDGE_DEBUG_MODE", str(self.config.debug_mode)))

        # Paths
        self.config.temp_dir = os.getenv("GEMINI_BRIDGE_TEMP_DIR", self.config.temp_dir)
        self.config.cache_dir = os.getenv("GEMINI_BRIDGE_CACHE_DIR", self.config.cache_dir)

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse a boolean value from string."""
        return value.lower() in ("true", "1", "yes", "on")

    def load(self) -> AppConfig:
        """Load configuration (already loaded in __init__)."""
        return self.config

    def get_temp_dir(self) -> Path:
        """Get absolute path to temp directory."""
        path = self.project_root / self.config.temp_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_cache_dir(self) -> Path:
        """Get absolute path to cache directory."""
        path = self.project_root / self.config.cache_dir
        path.mkdir(parents=True, exist_ok=True)
        return path