import io
import zipfile
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.tx10_ai.models.tx10_document_extractor import (
    _MAX_ZIP_MEMBER_BYTES,
    PHOTO_EXTENSIONS,
    _safe_zip_read,
    extract_text,
)


@tagged("post_install", "-at_install")
class TestTx10DocumentExtractor(TransactionCase):

    def test_photo_jpg_returns_empty(self):
        self.assertEqual(extract_text("photo.jpg", b"fake bytes"), "")

    def test_photo_png_returns_empty(self):
        self.assertEqual(extract_text("image.PNG", b"data"), "")

    def test_photo_extensions_set(self):
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff"):
            self.assertIn(ext, PHOTO_EXTENSIONS)

    def test_plain_text_extraction(self):
        text = extract_text("file.txt", b"hello world solar panel")
        self.assertEqual(text, "hello world solar panel")

    def test_csv_extraction(self):
        text = extract_text("data.csv", b"col1,col2\nval1,val2")
        self.assertIn("col1", text)

    def test_large_file_returns_empty(self):
        big = b"x" * (51 * 1024 * 1024)
        self.assertEqual(extract_text("big.txt", big), "")

    def test_unknown_extension_returns_empty(self):
        self.assertEqual(extract_text("archive.7z", b"binary data"), "")

    def test_zip_bomb_guard(self):
        # 51 MB of highly compressible data: the on-disk zip is tiny (~KB) but the
        # member decompresses past the 50 MB cap. extract_text must reject it
        # gracefully (empty string) rather than blow up worker memory or raise.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("word/document.xml", b"x" * (51 * 1024 * 1024))
        buf.seek(0)
        result = extract_text("fake.docx", buf.read())
        self.assertEqual(result, "")

    def test_extract_text_empty_bytes(self):
        self.assertEqual(extract_text("doc.txt", b""), "")

    def test_safe_zip_read_header_check_rejects_large_declared_size(self):
        # First guard: an honest header declaring > cap is rejected before any read.
        z = MagicMock(spec=zipfile.ZipFile)
        info = MagicMock()
        info.file_size = _MAX_ZIP_MEMBER_BYTES + 1
        z.getinfo.return_value = info
        with self.assertRaises(ValueError):
            _safe_zip_read(z, "word/document.xml")
        z.open.assert_not_called()

    def test_safe_zip_read_streaming_cap_rejects_lying_header(self):
        # Defense-in-depth: header lies small (passes line-55 check) but the
        # decompressed stream exceeds the cap. The capped read must catch it.
        z = MagicMock(spec=zipfile.ZipFile)
        info = MagicMock()
        info.file_size = 10  # lie — passes the header check
        z.getinfo.return_value = info
        fake_fh = MagicMock()
        fake_fh.read.return_value = b"x" * (_MAX_ZIP_MEMBER_BYTES + 1)
        z.open.return_value.__enter__.return_value = fake_fh
        with self.assertRaises(ValueError):
            _safe_zip_read(z, "word/document.xml")
        # Confirms the read was capped, not unbounded.
        fake_fh.read.assert_called_once_with(_MAX_ZIP_MEMBER_BYTES + 1)
