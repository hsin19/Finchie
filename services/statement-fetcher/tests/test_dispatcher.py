import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from finchie_statement_fetcher.dispatcher import (
    _extract_document,
    _extract_documents,
    _extract_source,
    process,
)
from finchie_statement_fetcher.models import Statement
from finchie_statement_fetcher.processor import BaseProcessor


class MockExtractor(BaseProcessor):
    _thread_local = threading.local()

    @classmethod
    def config_name(cls) -> str:
        return "mock_extractor"

    @classmethod
    def can_handle(cls, config, folder_path) -> bool:
        return getattr(cls._thread_local, "can_handle_result", False)

    @classmethod
    def extract(cls, config, folder_path):
        return getattr(cls._thread_local, "extract_result", None)

    @classmethod
    def set_state(cls, can_handle_result=False, extract_result=None):
        cls._thread_local.can_handle_result = can_handle_result
        cls._thread_local.extract_result = extract_result

    @classmethod
    def cleanup(cls) -> None:
        cls._thread_local.can_handle_result = False
        cls._thread_local.extract_result = None


@pytest.fixture(autouse=True)
def reset_mock_extractor():
    MockExtractor.cleanup()
    yield
    MockExtractor.cleanup()


@pytest.fixture
def mock_config():
    return {
        "source_extractors": {
            "output_dir": "test_output_dir",
            "gmail": {
                "query": "test_query",
                "days_ago": 7,
                "output_dir": "test_gmail_output",
                "disable": False,
            },
        },
        "document_extractors": {"mock_extractor": {"test_config": "test_value"}},
    }


@pytest.fixture
def mock_folders():
    return ["folder1", "folder2"]


@patch("finchie_statement_fetcher.dispatcher.fetch_gmail_messages")
def test_extract_source(mock_gmail_fetch, mock_config):
    """Test that _extract_source calls the gmail fetcher with correct config"""
    mock_gmail_fetch.return_value = ["test_folder1", "test_folder2"]

    result = _extract_source(mock_config)

    mock_gmail_fetch.assert_called_once()
    assert len(result) == 2
    assert "test_folder1" in result
    assert "test_folder2" in result


@patch("finchie_statement_fetcher.dispatcher.Path")
def test_extract_documents_nonexistent_folder(mock_path, mock_config, mock_folders):
    """Test that _extract_documents skips non-existent folders"""
    # Mock Path exists to return False
    mock_path_instance = MagicMock()
    mock_path_instance.exists.return_value = False
    mock_path.return_value = mock_path_instance

    result = _extract_documents(mock_config, mock_folders)

    assert len(result) == 0
    assert mock_path_instance.exists.call_count == 2


@patch("finchie_statement_fetcher.dispatcher.Path")
@patch("finchie_statement_fetcher.dispatcher._extract_document")
def test_extract_documents_success(mock_extract_document, mock_path, mock_config, mock_folders):
    """Test that _extract_documents processes existing folders correctly"""
    # Mock Path exists to return True
    mock_path_instance = MagicMock()
    mock_path_instance.exists.return_value = True
    mock_path.return_value = mock_path_instance

    # Mock _extract_document to return a Statement
    mock_bill = MagicMock(spec=Statement)
    mock_extract_document.return_value = mock_bill

    result = _extract_documents(mock_config, mock_folders)

    assert len(result) == 2
    assert result[0] == mock_bill
    assert result[1] == mock_bill
    assert mock_extract_document.call_count == 2


@patch("finchie_statement_fetcher.dispatcher.ALL_EXTRACTORS", [MockExtractor])
def test_extract_document_success():
    """Test that _extract_document finds the right extractor and extracts data"""
    config = {"mock_extractor": {"test_param": "test_value"}}
    folder_path = Path("test_folder")

    # Set up MockExtractor to return a bill
    mock_bill = MagicMock(spec=Statement)
    MockExtractor.set_state(can_handle_result=True, extract_result=mock_bill)
    result = _extract_document(config, folder_path)

    assert result == mock_bill


@patch("finchie_statement_fetcher.dispatcher.ALL_EXTRACTORS", [MockExtractor])
def test_extract_document_no_handler():
    """Test that _extract_document returns None when no extractor can handle the folder"""
    config = {"mock_extractor": {}}
    folder_path = Path("test_folder")

    # Set up MockExtractor to not handle any folders
    MockExtractor.set_state(can_handle_result=False, extract_result=None)
    result = _extract_document(config, folder_path)

    assert result is None


@patch("finchie_statement_fetcher.dispatcher.ALL_EXTRACTORS", [MockExtractor])
def test_extract_document_extract_failure():
    """Test that _extract_document tries all extractors and returns None when extraction fails"""
    config = {"mock_extractor": {}}
    folder_path = Path("test_folder")

    # Set up MockExtractor to handle folders but fail to extract
    MockExtractor.set_state(can_handle_result=True, extract_result=None)
    result = _extract_document(config, folder_path)

    assert result is None


@patch("finchie_statement_fetcher.dispatcher._extract_source")
@patch("finchie_statement_fetcher.dispatcher._extract_documents")
def test_process(mock_extract_documents, mock_extract_source, mock_config):
    """Test that process calls the extract functions with correct params"""
    mock_extract_source.return_value = ["test_folder1", "test_folder2"]
    mock_extract_documents.return_value = [MagicMock(spec=Statement)]

    process(mock_config)

    mock_extract_source.assert_called_once_with(mock_config)
    mock_extract_documents.assert_called_once_with(mock_config, ["test_folder1", "test_folder2"])
