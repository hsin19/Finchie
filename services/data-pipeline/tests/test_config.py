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
    """Test get_default_builder method of Config"""
    # Set test environment
    monkeypatch.setenv("ENV", "test")

    # Create test config directory
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create base config file
    base_config = {"server": {"host": "base-host", "port": 8000}, "database": "base-db"}
    with open(config_dir / "config.json", "w") as f:
        json.dump(base_config, f)

    # Create environment-specific config file
    env_config = {"server": {"host": "test-host"}, "log_level": "debug", "null_value": None}
    with open(config_dir / "config.test.json", "w") as f:
        json.dump(env_config, f)

    # Set environment variable overrides
    monkeypatch.setenv("SERVER__PORT", "9999")
    monkeypatch.setenv("EXTRA", "value")

    # Use default builder to build config
    builder = Config.get_default_builder(str(config_dir))
    config = builder.build()

    # Verify config merging and priorities
    assert config.get("server.host") == "test-host"  # From env-specific file
    assert config.get("server.port") == "9999"  # From environment variable
    assert config.get("database") == "base-db"  # From base config
    assert config.get("log_level") == "debug"  # From env-specific file
    assert config.get("extra") == "value"  # From environment variable
    assert config.get("null_value") is None  # From env-specific file
