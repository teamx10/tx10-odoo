import io
import os
import zipfile

try:
    from defusedxml.ElementTree import fromstring as _xml_fromstring
except ImportError:
    # defusedxml preferred; stdlib fallback is safe on Python 3.10+ (expat 2.4+)
    from xml.etree.ElementTree import fromstring as _xml_fromstring  # noqa: S405

try:
    from pypdf import PdfReader as _PdfReader
except ImportError:
    _PdfReader = None

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff"}

_MAX_ZIP_MEMBER_BYTES = 50 * 1024 * 1024
_MAX_CONTENT_BYTES = 50 * 1024 * 1024


def extract_text(filename: str, content_bytes: bytes) -> str:
    if len(content_bytes) > _MAX_CONTENT_BYTES:
        return ""
    ext = _get_ext(filename)
    if ext in PHOTO_EXTENSIONS:
        return ""
    if ext == ".pdf":
        return _extract_pdf(content_bytes)
    if ext == ".docx":
        return _extract_docx(content_bytes)
    if ext in (".xlsx", ".xls"):
        return _extract_xlsx(content_bytes)
    if ext in (".txt", ".csv", ".json", ".xml", ".yaml", ".yml", ".md"):
        return _decode_text(content_bytes)
    return ""


def _get_ext(filename: str) -> str:
    return os.path.splitext(filename.lower())[1]


def _decode_text(content_bytes: bytes) -> str:
    try:
        return content_bytes[:10000].decode("utf-8", errors="replace")
    except (UnicodeDecodeError, AttributeError):
        return ""


def _safe_zip_read(z: zipfile.ZipFile, member_name: str) -> bytes:
    info = z.getinfo(member_name)
    if info.file_size > _MAX_ZIP_MEMBER_BYTES:
        raise ValueError(f"Member {member_name!r} uncompressed size exceeds limit")
    return z.read(member_name)


def _extract_pdf(content_bytes: bytes) -> str:
    if _PdfReader is None:
        return ""
    try:
        reader = _PdfReader(io.BytesIO(content_bytes))
        return " ".join(p.extract_text() or "" for p in reader.pages[:3])
    except Exception:  # noqa: BLE001
        return ""


def _parse_docx_xml(data: bytes) -> str:
    tree = _xml_fromstring(data)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    texts = [t.text or "" for t in tree.findall(".//w:t", ns)]
    return " ".join(texts)[:10000]


def _extract_docx(content_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
            data = _safe_zip_read(z, "word/document.xml")
            return _parse_docx_xml(data)
    except Exception:  # noqa: BLE001
        return ""


def _parse_xlsx_xml(data: bytes) -> str:
    tree = _xml_fromstring(data)
    texts = [t.text or "" for t in tree.findall(".//{*}t")]
    return " ".join(texts[:500])[:10000]


def _extract_xlsx(content_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
            if "xl/sharedStrings.xml" not in z.namelist():
                return ""
            data = _safe_zip_read(z, "xl/sharedStrings.xml")
            return _parse_xlsx_xml(data)
    except Exception:  # noqa: BLE001
        return ""
