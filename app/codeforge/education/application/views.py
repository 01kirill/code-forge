from datetime import UTC, datetime

from codeforge.common.contracts import Document


def now() -> datetime:
    return datetime.now(UTC)


def expose(doc: Document, *hidden: str) -> Document:
    return {
        key: value for key, value in doc.items() if key != "id" and key not in hidden
    }
