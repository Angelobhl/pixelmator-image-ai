"""
Configuration management module.
Handles application settings and persistence.
"""

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


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
    """Configuration manager for loading and saving settings."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_dir = project_root / "config"
        self.default_config_path = self.config_dir / "default_config.json"
        self.user_config_path = self.config_dir / "user_config.json"
        self.config: AppConfig = AppConfig()

    def load(self) -> AppConfig:
        """Load configuration from files."""
        # Load default config first
        if self.default_config_path.exists():
            with open(self.default_config_path, 'r', encoding='utf-8') as f:
                default_data = json.load(f)
                self.config = AppConfig(**default_data)

        # Override with user config if exists
        if self.user_config_path.exists():
            with open(self.user_config_path, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
                # Merge user config into default
                for key, value in user_data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)

        return self.config

    def save(self) -> None:
        """Save current configuration to user config file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.user_config_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.config), f, indent=4, ensure_ascii=False)

    def reset(self) -> None:
        """Reset to default configuration."""
        if self.user_config_path.exists():
            self.user_config_path.unlink()
        self.config = AppConfig()
        self.load()

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