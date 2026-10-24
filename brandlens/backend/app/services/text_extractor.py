# text_extractor.py
# Pulls plain text out of an uploaded .txt, .pdf or .docx file.

import io


class ExtractError(Exception):
    """Raised when the file type is not supported or the file cannot be read."""


def extract_text(filename, data):
    """filename decides the type; data is the raw bytes of the file. Returns the text."""
    name = (filename or "").lower()

    try:
        if name.endswith(".txt"):
            return data.decode("utf-8", errors="replace").strip()

        if name.endswith(".pdf"):
            import pdfplumber

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = [(page.extract_text() or "") for page in pdf.pages]
            return "\n\n".join(pages).strip()

        if name.endswith(".docx"):
            import docx

            document = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in document.paragraphs).strip()
    except Exception as error:
        raise ExtractError(f"Could not read this file ({type(error).__name__}).") from error

    raise ExtractError("Unsupported file type. Please use .txt, .pdf or .docx.")
