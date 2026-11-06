from collections.abc import Sequence

from finchie_parser.documents import extract_pdfs
from finchie_parser.errors import UnsupportedDocumentError
from finchie_parser.model import ParseResult
from finchie_parser.ocr import Ocr
from finchie_parser.parsers import PARSERS, StatementParser
from finchie_parser.pdf import open_pdf


def parse_document(
    filename: str,
    content_type: str,
    content: bytes,
    *,
    passwords: Sequence[str],
    ocr: Ocr | None,
    parsers: Sequence[StatementParser] = PARSERS,
) -> ParseResult:
    attachments = extract_pdfs(filename, content_type, content)
    if not attachments:
        raise UnsupportedDocumentError("the document contains no PDF")

    # Trust the bank's attachment name when it is known: e-mails also carry payment slips and
    # other PDFs. Bare uploads with arbitrary names fall back to recognizing the text.
    by_name = [
        (attachment, parser)
        for attachment in attachments
        for parser in parsers
        if parser.matches_filename(attachment.filename)
    ]
    candidates = by_name or [(attachment, None) for attachment in attachments]

    for attachment, known in candidates:
        with open_pdf(attachment, passwords) as document:
            parser = known or next((p for p in parsers if p.matches_text(document)), None)
            if parser is None:
                continue
            parsed = parser.parse(document, ocr)
            return ParseResult(parser.name, parser.version, parsed.statement, parsed.warnings)

    names = ", ".join(attachment.filename for attachment in attachments)
    raise UnsupportedDocumentError(f"no parser recognizes {names}")
