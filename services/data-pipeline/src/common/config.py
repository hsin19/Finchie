import copy
import json
import os
from typing import Any


def _normalize_keys_to_lowercase(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively convert all dictionary keys to lowercase
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key.lower()] = _normalize_keys_to_lowercase(value)
        else:
            result[key.lower()] = value
    return result


class Config:
    """
    Immutable configuration class with case-insensitive keys
    """

    # Define __slots__ to prevent adding attributes after initialization
    __slots__ = ("_config",)

    def __init__(self, config_data: dict[str, Any] | None = None, *, _skip_normalization: bool = False):
        """
        Initialize Config with optional normalization

        Args:
            config_data: The configuration dictionary
            _skip_normalization: If True, skip keys normalization (internal use)
        """
        if config_data is None:
            self._config = {}
        elif _skip_normalization:
            self._config = config_data
        else:
            self._config = _normalize_keys_to_lowercase(config_data)

    def get(self, key: str, default: Any = None) -> Any:
        key = key.lower()

        # Handle nested keys with dot notation
        if "." in key:
            parts = key.split(".")
            current = self._config

            # Navigate through nested dictionaries
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    return default
                current = current[part]

            return current.get(parts[-1], default)
        else:
            return self._config.get(key, default)

    def get_string(self, key: str, default: str = "") -> str:
        value = self.get(key, default)
        try:
            return str(value)
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, None)

        if value is None:
            return default

        true_values = {"true", "yes", "1", 1}
        false_values = {"false", "no", "0", 0}

        if isinstance(value, str):
            value = value.lower().strip()

        if value in true_values:
            return True
        if value in false_values:
            return False

        return default

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get(key, None)
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        value = self.get(key, None)
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_list(self, key: str, default: list | None = None) -> list:
        if default is None:
            default = []

        value = self.get(key, default)
        if isinstance(value, list):
            return value
        return default

    def get_section(self, section_key: str) -> "Config":
        section_value = self.get(section_key, {})

        if not isinstance(section_value, dict):
            return Config({})

        return Config(section_value, _skip_normalization=True)

    def __getattr__(self, name: str) -> Any:
        name = name.lower()
        if name not in self._config:
            return None

        if isinstance(self._config[name], dict):
            return Config(self._config[name], _skip_normalization=True)
        return self._config[name]

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    @classmethod
    def get_default_builder(cls, config_dir: str = "config") -> "ConfigBuilder":
        """
        Get a ConfigBuilder with default configuration loading strategy

        Loading order (later sources override earlier ones):
        1. Base config file (config/config.json)
        2. Environment-specific config file (config.{ENV}.json)
        3. Environment variables
        """
        builder = ConfigBuilder()

        # Get current environment
        env = os.environ.get("ENV", "development")

        # Load configuration files and environment variables
        base_config_path = os.path.join(config_dir, "config.json")
        builder.with_json_file(base_config_path, optional=True)

        env_config_path = os.path.join(config_dir, f"config.{env}.json")
        builder.with_json_file(env_config_path, optional=True)

        builder.with_env()

        return builder


class ConfigBuilder:
    """
    Builder class for creating Config objects with case-insensitive keys
    """

    def __init__(self):
        self._config = {}

    def with_dict(self, config_data: dict[str, Any]) -> "ConfigBuilder":
        # Convert config_data keys to lowercase before updating
        lowercase_config = _normalize_keys_to_lowercase(config_data)
        self._deep_update(self._config, lowercase_config)
        return self

    def with_env(self) -> "ConfigBuilder":
        """
        Add configuration from environment variables
        Uses double underscore (__) as a separator for nested config.
        Example: DATABASE__HOST will be converted to config.database.host
        """

        for key, value in os.environ.items():
            # Convert key to lowercase
            key = key.lower()

            # Handle nested configuration with __ separator
            if "__" in key:
                parts = key.split("__")

                current = self._config
                for part in parts[:-1]:
                    part = part.lower()
                    if part not in current:
                        current[part] = {}
                    elif not isinstance(current[part], dict):
                        # If we encounter a non-dict value when we need a dict,
                        # overwrite it with an empty dict
                        current[part] = {}
                    current = current[part]

                # Set the value at the leaf node
                current[parts[-1].lower()] = value
            else:
                self._config[key] = value

        return self

    def with_json_file(self, file_path: str, optional: bool = False) -> "ConfigBuilder":
        if not os.path.exists(file_path):
            if optional:
                return self
            else:
                raise FileNotFoundError(f"Configuration file not found: {file_path}")

        try:
            with open(file_path) as f:
                config_data = json.load(f)
                return self.with_dict(config_data)
        except json.JSONDecodeError as err:
            raise ValueError(f"Invalid JSON format in file: {file_path}") from err

    @staticmethod
    def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                ConfigBuilder._deep_update(target[key], value)
            else:
                target[key] = value

    def build(self) -> Config:
        return Config(copy.deepcopy(self._config), _skip_normalization=True)
