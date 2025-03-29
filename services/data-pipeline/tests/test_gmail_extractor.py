import pytest

from finchie_data_pipeline.source_extractors import gmail_extractor

# Import required members from the module
GmailConfig = gmail_extractor.GmailConfig
_get_header = gmail_extractor._get_header
_get_credentials = gmail_extractor._get_credentials
GmailExtractorError = gmail_extractor.GmailExtractorError
extract_gmail_messages = gmail_extractor.extract_gmail_messages


def test_default_values():
    """Test if the default values of GmailConfig are correctly set"""
    config = GmailConfig()
    assert config.base64_token is None
    assert config.credentials_file == "config/secret/gmail/credentials.json"
    assert config.token_file == "config/secret/gmail/token.json"
    assert config.output_dir == "data/extract/gmail"
    assert config.query == ""
    assert config.days_ago == 30


def test_custom_values():
    """Test if GmailConfig can properly set custom values"""
    config = GmailConfig(
        base64_token="test_token",
        credentials_file="test_creds.json",
        token_file="test_token.json",
        output_dir="test_output",
        query="label:test",
        days_ago=15,
    )
    assert config.base64_token == "test_token"
    assert config.credentials_file == "test_creds.json"
    assert config.token_file == "test_token.json"
    assert config.output_dir == "test_output"
    assert config.query == "label:test"
    assert config.days_ago == 15


def test_get_header():
    """Test if the _get_header function can correctly extract email headers"""
    headers = [
        {"name": "From", "value": "sender@example.com"},
        {"name": "To", "value": "recipient@example.com"},
        {"name": "Subject", "value": "Test Email"},
    ]

    assert _get_header(headers, "From") == "sender@example.com"
    assert _get_header(headers, "To") == "recipient@example.com"
    assert _get_header(headers, "Subject") == "Test Email"
    assert _get_header(headers, "NonExistent") == ""


def test_get_credentials_from_file(mocker):
    """Test that _get_credentials loads credentials from file when no base64_token is provided"""
    # Mock os.path.exists to return True (file exists)
    mock_exists = mocker.patch("os.path.exists", return_value=True)

    # Mock Credentials.from_authorized_user_file
    mock_from_authorized_user_file = mocker.patch("google.oauth2.credentials.Credentials.from_authorized_user_file")

    # Create mock credentials object
    file_credentials = mocker.MagicMock()
    file_credentials.valid = True
    file_credentials.source = "file"
    mock_from_authorized_user_file.return_value = file_credentials

    # Execute the function
    config = GmailConfig(base64_token=None)
    result = _get_credentials(config)

    # Verify results
    assert result.source == "file"
    assert mock_exists.called
    assert mock_from_authorized_user_file.called


def test_get_credentials_from_base64_token(mocker):
    """Test that _get_credentials loads credentials from base64_token when provided"""
    # Mock base64.b64decode and json.loads
    mocker.patch("base64.b64decode", return_value=b'{"token": "test_token"}')
    mocker.patch("json.loads", return_value={"token": "test_token"})

    # Mock Credentials.from_authorized_user_info
    mock_from_authorized_user_info = mocker.patch("google.oauth2.credentials.Credentials.from_authorized_user_info")

    # Create mock credentials object
    token_credentials = mocker.MagicMock()
    token_credentials.valid = True
    token_credentials.source = "token"
    mock_from_authorized_user_info.return_value = token_credentials

    # Execute the function
    config = GmailConfig(base64_token="dummy_token")
    result = _get_credentials(config)

    # Verify results
    assert result.source == "token"
    assert mock_from_authorized_user_info.called


def test_extract_gmail_messages_authentication_error(mocker):
    """Test authentication error handling when processing messages"""
    # Patch the _get_credentials function directly
    mocker.patch.object(gmail_extractor, "_get_credentials", return_value=None)

    with pytest.raises(GmailExtractorError, match="Failed to obtain credentials"):
        extract_gmail_messages(GmailConfig(query="label:inbox"))
