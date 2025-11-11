import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class CalDAVConfig:
    server_url: str
    username: str
    password: str


@dataclass
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com"


@dataclass
class AppConfig:
    caldav: CalDAVConfig
    deepseek: Optional[DeepSeekConfig] = None
    
    def get(self, key: str, default: Any = None) -> Any:
        """提供类似字典的 get 方法以保持兼容性"""
        return getattr(self, key, default)


class ConfigManager:
    """Configuration manager with support for config_private.json and config.json."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.private_config_path = self.project_root / "config_private.json"
        self.default_config_path = self.project_root / "config.json"

    def load_config(self) -> AppConfig:
        """Load configuration with priority: config_private.json > config.json."""
        config_data = self._load_config_file()

        # Validate required CalDAV configuration
        if "caldav" not in config_data:
            raise ValueError("CalDAV configuration is required")

        caldav_config = CalDAVConfig(
            server_url=config_data["caldav"]["server_url"],
            username=config_data["caldav"]["username"],
            password=config_data["caldav"]["password"]
        )

        # Load DeepSeek configuration if available
        deepseek_config = None
        if "deepseek" in config_data and config_data["deepseek"]:
            deepseek_data = config_data["deepseek"]
            if "api_key" in deepseek_data and deepseek_data["api_key"]:
                deepseek_config = DeepSeekConfig(
                    api_key=deepseek_data["api_key"],
                    base_url=deepseek_data.get("base_url", "https://api.deepseek.com")
                )

        return AppConfig(caldav=caldav_config, deepseek=deepseek_config)

    def _load_config_file(self) -> Dict[str, Any]:
        """Load configuration from file with priority handling."""
        # Try config_private.json first
        if self.private_config_path.exists():
            logger.debug(f"Loading configuration from {self.private_config_path}")
            with open(self.private_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Fall back to config.json
        if self.default_config_path.exists():
            logger.debug(f"Loading configuration from {self.default_config_path}")
            with open(self.default_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # No configuration found
        raise FileNotFoundError(
            f"No configuration file found. Please create either {self.private_config_path} "
            f"or {self.default_config_path}"
        )


# Global config manager instance
_config_manager = None


def get_config() -> AppConfig:
    """Get the application configuration."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.load_config()