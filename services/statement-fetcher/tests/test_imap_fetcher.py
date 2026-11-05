import imaplib
import json
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest

from finchie_statement_fetcher.fetcher import imap

ImapConfig = imap.ImapConfig
ImapFetcherError = imap.ImapFetcherError
fetch_imap_messages = imap.fetch_imap_messages


# ---------- ImapConfig defaults ----------


def test_default_config_values():
    config = ImapConfig()
    assert config.host == "imap.gmail.com"
    assert config.port == 993
    assert config.user == ""
    assert config.password is None
    assert config.password_env_var == "IMAP_PASSWORD"
    assert config.mailbox == "INBOX"
    assert config.query == ""
    assert config.days_ago == 30
    assert config.output_dir == "data/fetched_result/imap"
    assert config.use_gmail_search is True
    assert config.timeout == 30


def test_custom_config_values():
    config = ImapConfig(
        host="imap.fastmail.com",
        port=143,
        user="me@example.com",
        password="pw",
        password_env_var="MY_PW",
        mailbox="Bills",
        query="from:bank",
        days_ago=7,
        output_dir="/tmp/out",
        use_gmail_search=False,
        timeout=10,
    )
    assert config.host == "imap.fastmail.com"
    assert config.port == 143
    assert config.user == "me@example.com"
    assert config.password == "pw"
    assert config.password_env_var == "MY_PW"
    assert config.mailbox == "Bills"
    assert config.query == "from:bank"
    assert config.days_ago == 7
    assert config.output_dir == "/tmp/out"
    assert config.use_gmail_search is False
    assert config.timeout == 10


# ---------- _resolve_password ----------


def test_resolve_password_prefers_env_var(monkeypatch):
    monkeypatch.setenv("IMAP_PASSWORD", "from-env")
    config = ImapConfig(password="from-config")
    assert imap._resolve_password(config) == "from-env"


def test_resolve_password_falls_back_to_config(monkeypatch):
    monkeypatch.delenv("IMAP_PASSWORD", raising=False)
    config = ImapConfig(password="from-config")
    assert imap._resolve_password(config) == "from-config"


def test_resolve_password_returns_none(monkeypatch):
    monkeypatch.delenv("IMAP_PASSWORD", raising=False)
    config = ImapConfig()
    assert imap._resolve_password(config) is None


def test_resolve_password_custom_env_var(monkeypatch):
    monkeypatch.setenv("MY_CUSTOM_PW", "secret")
    config = ImapConfig(password_env_var="MY_CUSTOM_PW")
    assert imap._resolve_password(config) == "secret"


# ---------- _build_search_criteria ----------


def test_build_search_criteria_with_gmail_query():
    config = ImapConfig(query="label:bill", days_ago=30, use_gmail_search=True)
    criteria = imap._build_search_criteria(config)
    assert criteria[0] == "X-GM-RAW"
    assert criteria[1] == '"label:bill"'
    assert criteria[2] == "SINCE"
    assert len(criteria) == 4  # X-GM-RAW, "...", SINCE, <date>


def test_build_search_criteria_with_standard_query():
    config = ImapConfig(query='FROM "bank.com"', use_gmail_search=False)
    criteria = imap._build_search_criteria(config)
    assert criteria[0] == 'FROM "bank.com"'
    assert criteria[1] == "SINCE"


def test_build_search_criteria_escapes_quotes():
    config = ImapConfig(query='from:"foo@bar.com" has:attachment', use_gmail_search=True)
    criteria = imap._build_search_criteria(config)
    # Embedded quotes need to be backslash-escaped so the outer pair stays intact
    assert criteria[1] == r'"from:\"foo@bar.com\" has:attachment"'


def test_build_search_criteria_no_query():
    config = ImapConfig(query="")
    criteria = imap._build_search_criteria(config)
    assert criteria == ["SINCE", criteria[1]]


# ---------- _sanitize_for_filename ----------


def test_sanitize_for_filename_keeps_safe_chars():
    assert imap._sanitize_for_filename("abc-123_def.eml", "fb") == "abc-123_def.eml"


def test_sanitize_for_filename_strips_unsafe_chars():
    assert imap._sanitize_for_filename("a/b<c>d", "fb") == "a_b_c_d"


def test_sanitize_for_filename_empty_falls_back():
    assert imap._sanitize_for_filename("", "fb") == "fb"
    assert imap._sanitize_for_filename("///", "fb") == "fb"


# ---------- _message_folder_name ----------


def _make_msg(headers: dict[str, str] | None = None):
    msg = MIMEMultipart()
    for k, v in (headers or {}).items():
        del msg[k]
        msg[k] = v
    return msg


def test_message_folder_name_uses_message_id():
    msg = _make_msg({"Message-ID": "<abc-123@example.com>"})
    name = imap._message_folder_name(b"42", msg)
    assert name == "abc-123_example.com"


def test_message_folder_name_falls_back_to_uid():
    msg = _make_msg()
    name = imap._message_folder_name(b"42", msg)
    assert name == "42"


def test_message_folder_name_truncates_long_id():
    long_id = "<" + ("a" * 200) + "@example.com>"
    msg = _make_msg({"Message-ID": long_id})
    name = imap._message_folder_name(b"42", msg)
    assert len(name) <= 80
    # Should still be deterministic — second call returns the same name
    assert imap._message_folder_name(b"42", msg) == name


# ---------- fetch_imap_messages: validation ----------


def test_fetch_raises_when_no_user(monkeypatch):
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    with pytest.raises(ImapFetcherError, match="No IMAP user"):
        fetch_imap_messages(ImapConfig(user=""))


def test_fetch_raises_when_no_password(monkeypatch):
    monkeypatch.delenv("IMAP_PASSWORD", raising=False)
    with pytest.raises(ImapFetcherError, match="No IMAP password"):
        fetch_imap_messages(ImapConfig(user="me@example.com"))


# ---------- fetch_imap_messages: integration with mocked IMAP ----------


@pytest.fixture
def mock_imap_client(mocker):
    """Patch imaplib.IMAP4_SSL so tests don't open real sockets."""
    client = mocker.MagicMock(name="IMAP4_SSL_instance")
    client.select.return_value = ("OK", [b"1"])
    client.uid.return_value = ("OK", [b""])
    client.logout.return_value = ("BYE", [b""])
    mocker.patch.object(imap.imaplib, "IMAP4_SSL", return_value=client)
    return client


def test_fetch_login_failure_raises(mock_imap_client, monkeypatch):
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    mock_imap_client.login.side_effect = imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    with pytest.raises(ImapFetcherError, match="IMAP login failed"):
        fetch_imap_messages(ImapConfig(user="me@example.com"))


def test_fetch_no_messages_returns_empty(mock_imap_client, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    mock_imap_client.uid.return_value = ("OK", [b""])

    result = fetch_imap_messages(ImapConfig(user="me@example.com", output_dir=str(tmp_path), query="label:bill"))
    assert result == []
    mock_imap_client.logout.assert_called_once()


def test_fetch_select_failure_raises(mock_imap_client, monkeypatch):
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    mock_imap_client.select.return_value = ("NO", [b"no such mailbox"])

    with pytest.raises(ImapFetcherError, match="Cannot select"):
        fetch_imap_messages(ImapConfig(user="me@example.com", mailbox="Nope"))


def _build_raw_email_with_pdf(filename: str = "TSB_Creditcard_Estatement_202502.pdf") -> bytes:
    msg = MIMEMultipart()
    msg["Subject"] = "Your Bill"
    msg["From"] = "bank@example.com"
    msg["To"] = "me@example.com"
    msg["Message-ID"] = "<bill-202502@example.com>"
    msg["Date"] = "Wed, 1 Feb 2025 00:00:00 +0000"
    msg.attach(MIMEText("plain body text", "plain", "utf-8"))
    pdf_part = MIMEApplication(b"%PDF-1.4 dummy", _subtype="pdf")
    pdf_part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(pdf_part)
    return msg.as_bytes()


def test_fetch_saves_attachment_and_metadata(mock_imap_client, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    raw_email = _build_raw_email_with_pdf()

    def uid_side_effect(command, *args):
        if command == "SEARCH":
            return ("OK", [b"1001"])
        if command == "FETCH":
            return ("OK", [(b"1001 (RFC822 {size})", raw_email)])
        return ("NO", [b"unknown"])

    mock_imap_client.uid.side_effect = uid_side_effect

    folders = fetch_imap_messages(
        ImapConfig(
            user="me@example.com",
            output_dir=str(tmp_path),
            query="label:bill",
        )
    )

    assert len(folders) == 1
    folder = folders[0]
    assert os.path.exists(folder)
    # PDF attachment is what TsibProcessor consumes
    pdf_files = [f for f in os.listdir(folder) if f.endswith(".pdf")]
    assert pdf_files == ["TSB_Creditcard_Estatement_202502.pdf"]
    # Metadata sidecar
    with open(os.path.join(folder, "message.json"), encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["subject"] == "Your Bill"
    assert meta["message_id"] == "<bill-202502@example.com>"
    # Plaintext body persisted for debugging
    with open(os.path.join(folder, "body.txt"), encoding="utf-8") as f:
        assert "plain body text" in f.read()


def test_fetch_skips_signature_attachments(mock_imap_client, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAP_PASSWORD", "pw")

    msg = MIMEMultipart()
    msg["Subject"] = "Signed"
    msg["Message-ID"] = "<sig@example.com>"
    msg.attach(MIMEText("body", "plain", "utf-8"))
    sig = MIMEApplication(b"signature-bytes", _subtype="pkcs7-signature")
    sig.add_header("Content-Disposition", "attachment", filename="smime.p7s")
    msg.attach(sig)
    raw_email = msg.as_bytes()

    def uid_side_effect(command, *args):
        if command == "SEARCH":
            return ("OK", [b"42"])
        if command == "FETCH":
            return ("OK", [(b"42 (RFC822 {size})", raw_email)])
        return ("NO", [b"unknown"])

    mock_imap_client.uid.side_effect = uid_side_effect

    folders = fetch_imap_messages(ImapConfig(user="me@example.com", output_dir=str(tmp_path)))

    assert len(folders) == 1
    assert "smime.p7s" not in os.listdir(folders[0])


def test_fetch_accepts_dict_config(mock_imap_client, monkeypatch, tmp_path):
    """coerce_to_instance should accept a dict and produce the same behaviour."""
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    mock_imap_client.uid.return_value = ("OK", [b""])

    result = fetch_imap_messages(
        {
            "user": "me@example.com",
            "output_dir": str(tmp_path),
            "query": "label:bill",
            "days_ago": 7,
        }
    )
    assert result == []
    # Ensure connection used the dict-derived config
    imap.imaplib.IMAP4_SSL.assert_called_once_with("imap.gmail.com", 993, timeout=30)
