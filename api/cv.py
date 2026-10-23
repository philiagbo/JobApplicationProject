import io

import docx
import pypdf

MAX_TEXT_CHARS = 200000
_UNREADABLE = "Couldn't read text from this CV"


def read_cv_text(data: bytes, kind: str) -> str:
    """kind is "pdf" or "docx". Raises ValueError("Couldn't read text from this CV") on any failure or empty text."""
    try:
        if kind == "pdf":
            reader = pypdf.PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        else:
            parts = []
            # document order matters: contact details in a top table must not land under a later Skills heading
            for block in docx.Document(io.BytesIO(data)).iter_inner_content():
                if hasattr(block, "rows"):
                    parts.extend(c.text for row in block.rows for c in row.cells)
                else:
                    parts.append(block.text)
            text = "\n".join(parts)
    except Exception as e:  # untrusted bytes: encrypted PDFs raise at extract_text, not at open
        raise ValueError(_UNREADABLE) from e
    text = text[:MAX_TEXT_CHARS].strip()
    if not text:
        raise ValueError(_UNREADABLE)
    return text
