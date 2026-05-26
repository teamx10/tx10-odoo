import io
import os
import xml.etree.ElementTree as ET
import zipfile

try:
    from pypdf import PdfReader as _PdfReader
except ImportError:
    from PyPDF2 import PdfReader as _PdfReader  # type: ignore[no-redef]

KEYWORD_RULES = {
    "SOLAR_MODULE": [
        "solar panel", "solar module", "pv module", "photovoltaic",
        "сонячна панель", "сонячний модуль", "фотоелектричний", "pv panel",
        "монокристал", "полікристал", "monocrystalline", "polycrystalline",
        "jinko", "longi", "canadian solar", "ja solar", "risen",
    ],
    "INVERTER": [
        "inverter", "інвертор", "grid-tie", "string inverter",
        "sma", "fronius", "huawei luna", "solaredge", "growatt",
        "on-grid", "off-grid",
        "hybrid inverter", "гібридний інвертор", "гібрид",
    ],
    "BATTERY": [
        "battery", "акумулятор", "акумуляторна батарея", "lithium",
        "lifepo4", "byd", "pylontech", "battery storage", "накопичувач енергії",
        "energy storage", "ємність акумулятора",
    ],
    "BMS": [
        "bms", "battery management", "pdu", "управління акумулятором",
        "балансування", "balance", "charge controller",
    ],
    "BOS": [
        "mounting", "структура кріплення", "рейка", "rail", "cable",
        "connector", "mc4", "combiner box", "disconnect switch",
        "захисний пристрій", "bos",
    ],
    "CONSUMPTION": [
        "consumption", "invoice", "рахунок", "споживання", "тариф",
        "electricity bill", "рахунок за електроенергію", "kwh",
        "лічильник", "meter", "навантаження", "load profile",
    ],
    "PERMIT": [
        "permit", "contract", "договір", "ту", "технічні умови",
        "agreement", "технічне завдання", "дозвіл", "обліковий",
        "meter agreement", "підключення до мережі",
    ],
    "SCHEME": [
        "scheme", "schematic", "схема", "wiring diagram", "однолінійна",
        "single line", "plan", "план", "layout", "розташування",
    ],
    "PVSYST": [
        "pvsyst", "pv syst", "simulation", "yield", "pr ratio",
        "performance ratio", "годовий виробіток", "annual yield",
        "pvgis", "метеодані", "irradiance",
    ],
    "SURVEY": [
        "questionnaire", "опитувальний лист", "survey", "анкета",
        "технічне завдання клієнта", "вимоги замовника",
    ],
}

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff"}

CATEGORY_TO_FOLDER_CODE = {
    "SOLAR_MODULE": "01_Сонячні_модулі",
    "INVERTER":     "02_Інвертори",
    "BATTERY":      "03_Акумулятори",
    "BMS":          "04_BMS_PDU",
    "BOS":          "05_BOS_обладнання",
    "PHOTO":        "01_Фото",
    "SCHEME":       "02_Схеми",
    "CONSUMPTION":  "03_Споживання_та_рахунки",
    "PERMIT":       "04_ТУ_договори_облік",
    "PVSYST":       "pvsyst_reports",
    "SURVEY":       "survey_orig",
    "UNKNOWN":      "05_Інше",
}

CONFIDENCE_THRESHOLD = 0.70

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


def classify(text: str, filename: str) -> dict:
    ext = _get_ext(filename)

    if ext in PHOTO_EXTENSIONS:
        return {
            "category": "01_Фото",
            "confidence": 1.0,
            "reasons": ["photo by extension"],
            "document_type_code": "photo",
        }

    corpus = f" {filename} {text} ".casefold()
    has_text = bool(text.strip())

    scores = {}
    reasons_map = {}

    for category, keywords in KEYWORD_RULES.items():
        score = 0
        matched = []
        for kw in keywords:
            if kw.casefold() in corpus:
                score += 1
                matched.append(kw)
        if score > 0:
            scores[category] = score
            reasons_map[category] = matched

    if not scores:
        return {
            "category": "05_Інше",
            "confidence": 0.65,
            "reasons": [],
            "document_type_code": "unknown",
        }

    best_cat = max(scores, key=lambda c: scores[c])
    best_score = scores[best_cat]

    confidence = 0.65 + 0.1 * min(best_score, 3)
    if has_text:
        confidence = max(confidence, 0.80)

    if confidence < CONFIDENCE_THRESHOLD:
        best_cat = "UNKNOWN"

    folder_code = CATEGORY_TO_FOLDER_CODE.get(best_cat, "05_Інше")

    return {
        "category": folder_code,
        "confidence": confidence,
        "reasons": reasons_map.get(best_cat, []),
        "document_type_code": best_cat.lower(),
    }


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
    try:
        reader = _PdfReader(io.BytesIO(content_bytes))
        return " ".join(p.extract_text() or "" for p in reader.pages[:3])
    except Exception:  # noqa: BLE001
        return ""


def _parse_docx_xml(data: bytes) -> str:
    tree = ET.fromstring(data)
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
    tree = ET.fromstring(data)
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
