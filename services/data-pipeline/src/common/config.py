import copy
import dataclasses
import importlib.util
import json
import os
import sys
from typing import Any


def _normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively convert all dictionary keys to lowercase and values to strings or None
    Excludes callables (functions, lambdas, etc.) at any nesting level
    """
    result = {}
    for key, value in data.items():
        key = key.lower()

        if callable(value):
            continue

        if dataclasses.is_dataclass(value):
            value = dataclasses.asdict(value)

        if isinstance(value, dict):
            normalized_dict = _normalize_config(value)
            if normalized_dict:
                result[key] = normalized_dict
        elif value is None:
            result[key] = None
        else:
            result[key] = str(value)

    return result


class Config:
    """
    Immutable configuration class with case-insensitive keys and string/None values
    """

    # Define __slots__ to prevent adding attributes after initialization
    __slots__ = ("_config",)

    def __init__(self, config_data: dict[str, Any] | None = None, *, _skip_normalization: bool = False):
        """
        Initialize Config with normalized data (lowercase keys and string/None values)

        Args:
            config_data: The configuration dictionary
            _skip_normalization: If True, skip keys normalization (internal use)
        """
        if config_data is None:
            self._config = {}
        elif _skip_normalization:
            self._config = config_data
        else:
            self._config = _normalize_config(config_data)

    def get(self, key: str = "", default: Any = None) -> Any:
        if not key:
            return self._config

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

    def get_section(self, section_key: str) -> "Config":
        section_key = section_key.lower()
        if section_key not in self._config:
            return Config({})

        section_value = self._config[section_key]
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
        2. Base Python file (config/config.py)
        3. Environment-specific config file (config.{ENV}.json)
        4. Environment-specific Python file (config.{ENV}.py)
        5. Environment variables
        """
        builder = ConfigBuilder()

        # Get current environment
        env = os.environ.get("ENV", "development")

        # Load configuration files and environment variables
        base_config_path = os.path.join(config_dir, "config.json")
        builder.with_json_file(base_config_path, optional=True)

        py_config_path = os.path.join(config_dir, "config.py")
        builder.with_py_file(py_config_path, optional=True)

        env_config_path = os.path.join(config_dir, f"config.{env}.json")
        builder.with_json_file(env_config_path, optional=True)

        env_py_config_path = os.path.join(config_dir, f"config.{env}.py")
        builder.with_py_file(env_py_config_path, optional=True)

        builder.with_env()

        return builder


class ConfigBuilder:
    """
    Builder class for creating Config objects with case-insensitive keys
    """

    def __init__(self):
        self._config = {}

    def with_dict(self, config_data: dict[str, Any]) -> "ConfigBuilder":
        normalized_config = _normalize_config(config_data)
        self._deep_update(self._config, normalized_config)
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

    def with_py_file(self, file_path: str, optional: bool = False) -> "ConfigBuilder":
        """
        Add configuration from a Python file

        The Python file should define variables as uppercase constants:

        Example:
            ```
            # config.dev.py
            DEBUG = True
            DATABASE = {"HOST": "localhost", "PORT": 5432}
            ```
        Args:
            file_path: Path to the Python file
            optional: If True, do not raise an error if the file doesn't exist and return self

        Returns:
            self for chaining

        Raises:
            FileNotFoundError: If the file doesn't exist and optional is False
            ValueError: If there's an error loading or parsing the Python file
        """
        if not os.path.exists(file_path):
            if optional:
                return self
            else:
                raise FileNotFoundError(f"Configuration file not found: {file_path}")

        try:
            # Import the Python file as a module
            module_name = os.path.basename(file_path).replace(".py", "")
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None:
                raise ImportError(f"Could not load spec for module {module_name} from {file_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)  # type: ignore

            # Extract uppercase variables as configuration
            config_dict = {}
            for key in dir(module):
                # Skip internal/private attributes
                if key.startswith("__"):
                    continue

                # Get only uppercase variables as config entries
                if key.isupper():
                    config_dict[key] = getattr(module, key)

            return self.with_dict(config_dict)

        except Exception as e:
            if optional:
                return self
            raise ValueError(f"Error loading Python config file: {file_path}, error: {e!s}") from e

    def with_json_file(self, file_path: str, optional: bool = False) -> "ConfigBuilder":
        """
        Add configuration from a JSON file

        Args:
            file_path: Path to the JSON file
            optional: If True, do not raise an error if the file doesn't exist and return self

        Returns:
            self for chaining

        Raises:
            FileNotFoundError: If the file doesn't exist and optional is False
            ValueError: If there's an error parsing the JSON file
        """
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
