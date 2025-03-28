import json

import pytest

from src.common.config import Config, ConfigBuilder


@pytest.fixture
def sample_config_dict():
    return {
        "server": {"host": "localhost", "port": 8080, "debug": True},
        "database": {"url": "postgres://user:pass@localhost:5432/db", "pool_size": 5, "timeout": 30.5},
        "feature_flags": {"new_ui": True, "beta_features": False},
        "log_level": "info",
        "max_connections": 100,
        "tags": ["dev", "test", "local"],
        "empty_value": None,
    }


@pytest.fixture
def config_instance(sample_config_dict):
    return Config(sample_config_dict)


def test_config_empty():
    """Test empty Config instantiation"""
    config = Config()
    assert config.get("non_existent") is None
    assert config.get("non_existent", "default") == "default"


def test_config_get_basic(config_instance):
    """Test basic get method"""
    assert config_instance.get("log_level") == "info"
    assert config_instance.get("max_connections") == "100"
    assert config_instance.get("non_existent") is None
    assert config_instance.get("non_existent", "default") == "default"
    assert config_instance.get("empty_value") is None


def test_config_get_case_insensitive(config_instance):
    """Test case insensitivity of get method"""
    assert config_instance.get("LOG_LEVEL") == "info"
    assert config_instance.get("Max_Connections") == "100"


def test_config_get_nested(config_instance):
    """Test get method with nested keys"""
    assert config_instance.get("server.host") == "localhost"
    assert config_instance.get("server.port") == "8080"
    assert config_instance.get("database.pool_size") == "5"
    assert config_instance.get("database.timeout") == "30.5"
    assert config_instance.get("server.non_existent") is None
    assert config_instance.get("non_existent.key") is None


def test_config_get_nested_case_insensitive(config_instance):
    """Test case insensitivity of get method with nested keys"""
    assert config_instance.get("SERVER.HOST") == "localhost"
    assert config_instance.get("Database.Pool_Size") == "5"


def test_get_section(config_instance):
    """Test get_section method"""
    server_section = config_instance.get_section("server")
    assert isinstance(server_section, Config)
    assert server_section.get("host") == "localhost"
    assert server_section.get("port") == "8080"
    assert server_section.get("debug") == "True"

    # Test non-existent section
    non_existent_section = config_instance.get_section("non_existent")
    assert isinstance(non_existent_section, Config)
    assert non_existent_section.get("anything") is None

    # Test non-dictionary section
    non_dict_section = config_instance.get_section("log_level")  # log_level is a string
    assert isinstance(non_dict_section, Config)
    assert non_dict_section.get("anything") is None


def test_attribute_access(config_instance):
    """Test attribute access syntax"""
    assert config_instance.log_level == "info"
    assert config_instance.max_connections == "100"
    assert config_instance.server.host == "localhost"
    assert config_instance.server.port == "8080"
    assert config_instance.non_existent is None
    assert config_instance.empty_value is None

    # Test case insensitivity of attribute access
    assert config_instance.LOG_LEVEL == "info"
    assert config_instance.Server.Host == "localhost"


def test_item_access(config_instance):
    """Test item access syntax"""
    assert config_instance["log_level"] == "info"
    assert config_instance["max_connections"] == "100"
    assert config_instance["server.host"] == "localhost"
    assert config_instance["server.port"] == "8080"
    assert config_instance["non_existent"] is None
    assert config_instance["empty_value"] is None

    # Test case insensitivity of item access
    assert config_instance["LOG_LEVEL"] == "info"
    assert config_instance["SERVER.HOST"] == "localhost"


def test_config_builder_with_dict():
    """Test with_dict method of ConfigBuilder"""
    config_data = {"SERVER": {"HOST": "localhost", "PORT": 8080}, "DATABASE": "sqlite:///db.sqlite", "NULL_VALUE": None}

    builder = ConfigBuilder()
    builder.with_dict(config_data)
    config = builder.build()

    assert config.get("server.host") == "localhost"
    assert config.get("server.port") == "8080"
    assert config.get("database") == "sqlite:///db.sqlite"
    assert config.get("null_value") is None


def test_config_builder_with_env(monkeypatch):
    """Test with_env method of ConfigBuilder"""
    # Set environment variables
    monkeypatch.setenv("SERVER__HOST", "test-host")
    monkeypatch.setenv("SERVER__PORT", "9000")
    monkeypatch.setenv("DATABASE_URL", "mysql://user:pass@localhost/db")
    monkeypatch.setenv("DEBUG", "true")

    builder = ConfigBuilder()
    builder.with_env()
    config = builder.build()

    assert config.get("server.host") == "test-host"
    assert config.get("server.port") == "9000"
    assert config.get("database_url") == "mysql://user:pass@localhost/db"
    assert config.get("debug") == "true"


def test_config_builder_with_py_file(tmp_path):
    """Test with_py_file method of ConfigBuilder"""
    # Create test Python config file
    config_file = tmp_path / "test_config.py"
    with open(config_file, "w") as f:
        f.write("""
# Test config file
DEBUG = True
SERVER = {
    "HOST": "py-host",
    "PORT": 1234
}
DATABASE_URL = "postgres://user:password@localhost/testdb"
EMPTY_VALUE = None
lowercase_value = "this should be ignored"
        """)

    # Test reading existing file
    builder = ConfigBuilder()
    builder.with_py_file(str(config_file))
    config = builder.build()

    assert config.get("debug") == "True"
    assert config.get("server.host") == "py-host"
    assert config.get("server.port") == "1234"
    assert config.get("database_url") == "postgres://user:password@localhost/testdb"
    assert config.get("empty_value") is None
    # Lowercase values should be ignored
    assert config.get("lowercase_value") is None

    # Test reading non-existent file (non-optional)
    non_existent_file = tmp_path / "non_existent.py"
    builder = ConfigBuilder()
    with pytest.raises(FileNotFoundError):
        builder.with_py_file(str(non_existent_file))

    # Test reading non-existent file (optional)
    builder = ConfigBuilder()
    builder.with_py_file(str(non_existent_file), optional=True)
    config = builder.build()
    assert config.get("anything") is None

    # Test invalid Python file
    invalid_py_file = tmp_path / "invalid.py"
    with open(invalid_py_file, "w") as f:
        f.write("This is not valid Python x y z")

    builder = ConfigBuilder()
    with pytest.raises(ValueError):
        builder.with_py_file(str(invalid_py_file))


def test_py_file_with_imports_and_type_hints(tmp_path, monkeypatch):
    """Test Python config file with imports and type hints"""
    # Create test Python config file with imports and type hints
    complex_config_file = tmp_path / "complex_config.py"
    with open(complex_config_file, "w") as f:
        f.write(r"""
# Complex config file with imports and type hints
import os
import re
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta

# Constants with type hints
DEBUG: bool = True
LOG_LEVEL: str = "debug"
MAX_RETRIES: int = 5
TIMEOUT: float = 30.5

# Complex structure with type hints
DATABASE: Dict[str, Union[str, int, bool]] = {
    "HOST": os.environ.get("DB_HOST", "localhost"),
    "PORT": int(os.environ.get("DB_PORT", "5432")),
    "USER": "admin",
    "PASSWORD": "password123",
    "POOL_SIZE": 10,
    "SSL": True
}

# List with computed values
ALLOWED_HOSTS: List[str] = [
    "localhost",
    "127.0.0.1",
    f"{os.environ.get('APP_NAME', 'app')}.example.com"
]

# Generated value with computation
EXPIRES_AT: str = (datetime.now() + timedelta(days=30)).isoformat()

# Regex pattern
EMAIL_PATTERN: str = re.compile(r"[^@]+@[^@]+\.[^@]+").pattern

# Function that returns a value (should NOT be included)
def get_secret():
    return "secret-value"

# Callable should be excluded
API_HANDLER = lambda x: x * 2

# Class should be excluded
class ConfigItem:
    def __init__(self, value):
        self.value = value

# Private/lowercase variable should be excluded
_private_var = "private"
lowercase_setting = "ignore me"
        """)

    # Set environment variable for testing
    monkeypatch.setenv("DB_HOST", "test-db-host")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.delenv("APP_NAME", False)  # Ensure APP_NAME is not set

    # Test reading the file with imports and type hints
    builder = ConfigBuilder()
    builder.with_py_file(str(complex_config_file))
    config = builder.build()

    # Basic values
    assert config.get("debug") == "True"
    assert config.get("log_level") == "debug"
    assert config.get("max_retries") == "5"
    assert config.get("timeout") == "30.5"

    # Complex dictionary
    assert config.get("database.host") == "test-db-host"  # From environment variable
    assert config.get("database.port") == "5433"  # From environment variable
    assert config.get("database.user") == "admin"
    assert config.get("database.password") == "password123"
    assert config.get("database.pool_size") == "10"
    assert config.get("database.ssl") == "True"

    # List with computed values
    assert "localhost" in str(config.get("allowed_hosts"))
    assert "127.0.0.1" in str(config.get("allowed_hosts"))
    assert "app.example.com" in str(config.get("allowed_hosts"))  # APP_NAME is None, so it should be "app"

    # Generated value (exact value will vary but should exist)
    assert config.get("expires_at") is not None

    # Regex pattern
    assert config.get("email_pattern") is not None

    # These should NOT be in the config
    assert config.get("get_secret") is None
    assert config.get("api_handler") is None
    assert config.get("configitem") is None
    assert config.get("_private_var") is None
    assert config.get("lowercase_setting") is None


def test_config_builder_with_json_file(tmp_path):
    """Test with_json_file method of ConfigBuilder"""
    # Create test JSON file
    config_file = tmp_path / "test_config.json"
    config_data = {"server": {"host": "test-host", "port": 9000}, "database": "test-db", "debug": True, "null_value": None}

    with open(config_file, "w") as f:
        json.dump(config_data, f)

    # Test reading existing file
    builder = ConfigBuilder()
    builder.with_json_file(str(config_file))
    config = builder.build()

    assert config.get("server.host") == "test-host"
    assert config.get("server.port") == "9000"
    assert config.get("database") == "test-db"
    assert config.get("debug") == "True"
    assert config.get("null_value") is None

    # Test reading non-existent file (non-optional)
    non_existent_file = tmp_path / "non_existent.json"
    builder = ConfigBuilder()
    with pytest.raises(FileNotFoundError):
        builder.with_json_file(str(non_existent_file))

    # Test reading non-existent file (optional)
    builder = ConfigBuilder()
    builder.with_json_file(str(non_existent_file), optional=True)
    config = builder.build()
    assert config.get("anything") is None

    # Test invalid JSON file
    invalid_json_file = tmp_path / "invalid.json"
    with open(invalid_json_file, "w") as f:
        f.write("This is not valid JSON")

    builder = ConfigBuilder()
    with pytest.raises(ValueError, match="Invalid JSON format in file"):
        builder.with_json_file(str(invalid_json_file))


def test_config_builder_default_builder(monkeypatch, tmp_path):
    """Test get_default_builder method of Config with Python file support"""
    # Set test environment
    monkeypatch.setenv("ENV", "test")

    # Create test config directory
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create base config file
    base_config = {"server": {"host": "base-host", "port": 8000}, "database": "base-db"}
    with open(config_dir / "config.json", "w") as f:
        json.dump(base_config, f)

    # Create environment-specific JSON config file
    env_config = {"server": {"host": "json-host"}, "log_level": "debug", "null_value": None}
    with open(config_dir / "config.test.json", "w") as f:
        json.dump(env_config, f)

    # Create environment-specific Python config file (should override JSON)
    with open(config_dir / "config.test.py", "w") as f:
        f.write("""
# Test environment config
from typing import Dict, Any
import os

SERVER: Dict[str, Any] = {
    "HOST": "py-host"
}
ANOTHER_SETTING = "from-python"
        """)

    # Set environment variable overrides (highest priority)
    monkeypatch.setenv("SERVER__PORT", "9999")
    monkeypatch.setenv("EXTRA", "value")

    # Use default builder to build config
    builder = Config.get_default_builder(str(config_dir))
    config = builder.build()

    # Verify config merging and priorities
    assert config.get("server.host") == "py-host"  # From Python file (overrides JSON)
    assert config.get("server.port") == "9999"  # From environment variable
    assert config.get("database") == "base-db"  # From base config
    assert config.get("log_level") == "debug"  # From env-specific JSON file
    assert config.get("extra") == "value"  # From environment variable
    assert config.get("null_value") is None  # From env-specific JSON file
    assert config.get("another_setting") == "from-python"  # From Python file
