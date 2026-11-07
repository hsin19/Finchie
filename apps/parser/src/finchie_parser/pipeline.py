from collections.abc import Sequence

from finchie_parser.documents import extract_pdfs
from finchie_parser.errors import InvalidDocumentError, PasswordRequiredError, UnsupportedDocumentError
from finchie_parser.model import ParseResult
from finchie_parser.ocr import Ocr
from finchie_parser.parsers import PARSERS, StatementParser
from finchie_parser.pdf import PdfDocument, PdfSet


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
    with PdfSet(attachments, passwords) as pdfs:
        index, parser = select_statement(pdfs, parsers)
        parsed = parser.parse(pdfs.open(index), ocr)
    return ParseResult(parser.name, parser.version, parsed.statement, parsed.warnings)


def select_statement(pdfs: PdfSet, parsers: Sequence[StatementParser]) -> tuple[int, StatementParser]:
    """The index of the PDF that is the statement, and its parser. Parsing and reading both pick with it.

    In order of preference:

    1. A PDF whose name a parser knows and whose text that parser recognizes. E-mails also carry
       payment slips and notices; a name alone proves nothing, since any upload can be called that.
    2. A PDF whose name a parser knows but that cannot be opened to check; `pdfs.open` on it raises
       why. Its missing password is the error to report, not whatever parsing another attachment that
       names the bank, such as the payment slip, would give.
    3. Any PDF a parser recognizes by its text, skipping those that cannot be opened.

    With none, raises PasswordRequiredError if a PDF was locked, else InvalidDocumentError if one was
    unreadable, else UnsupportedDocumentError.
    """
    failed: dict[int, PasswordRequiredError | InvalidDocumentError] = {}

    def opened(index: int) -> PdfDocument | None:
        try:
            return pdfs.open(index)
        except (PasswordRequiredError, InvalidDocumentError) as error:
            failed[index] = error
            return None

    named = [(i, p) for i, a in enumerate(pdfs.attachments) for p in parsers if p.matches_filename(a.filename)]
    for index, parser in named:
        document = opened(index)
        if document is not None and parser.matches_text(document):
            return index, parser
    if unopened := [(index, parser) for index, parser in named if index in failed]:
        return min(unopened, key=lambda pick: _rank(failed[pick[0]]))

    for index in range(len(pdfs)):
        document = opened(index)
        if document is not None and (parser := next((p for p in parsers if p.matches_text(document)), None)):
            return index, parser

    if failed:
        raise min(failed.values(), key=_rank)
    names = ", ".join(attachment.filename for attachment in pdfs.attachments)
    raise UnsupportedDocumentError(f"no parser recognizes {names}")


def _rank(error: PasswordRequiredError | InvalidDocumentError) -> int:
    # A missing password is the one failure the owner can fix.
    return 0 if isinstance(error, PasswordRequiredError) else 1
