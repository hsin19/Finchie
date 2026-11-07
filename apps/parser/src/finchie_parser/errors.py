"""Errors that map onto gRPC status codes (ADR 0005). Anything else is a bug."""


class ParserError(Exception):
    pass


class UnsupportedDocumentError(ParserError):
    """No parser recognizes the document. Retrying cannot help."""


class InvalidDocumentError(ParserError):
    """The bytes are not a readable e-mail or PDF."""


class PasswordRequiredError(ParserError):
    """The PDF is encrypted and none of the configured passwords open it."""


class LayoutError(ParserError):
    """A recognized statement no longer matches its parser: the bank changed the layout."""
