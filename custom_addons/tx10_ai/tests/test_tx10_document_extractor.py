import io
import unittest
import zipfile

from odoo.addons.tx10_ai.models.tx10_document_extractor import (
    PHOTO_EXTENSIONS,
    extract_text,
)


class TestTx10DocumentExtractor(unittest.TestCase):

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
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            info = zipfile.ZipInfo("word/document.xml")
            info.file_size = 60 * 1024 * 1024  # 60 MB > 50 MB limit (zip bomb simulation)
            zf.writestr(info, b"<w:document/>")
        buf.seek(0)
        # Must not raise — graceful empty return
        result = extract_text("fake.docx", buf.read())
        self.assertEqual(result, "")

    def test_extract_text_empty_bytes(self):
        self.assertEqual(extract_text("doc.txt", b""), "")
