import unittest

from odoo.addons.tx10_ai.models.tx10_document_classifier import classify, extract_text


class TestTx10DocumentClassifier(unittest.TestCase):

    # --- classify() by extension ---

    def test_photo_jpg(self):
        result = classify("", "photo.jpg")
        self.assertEqual(result["category"], "01_Фото")
        self.assertEqual(result["confidence"], 1.0)

    def test_photo_png(self):
        result = classify("", "image.PNG")
        self.assertEqual(result["category"], "01_Фото")
        self.assertEqual(result["confidence"], 1.0)

    def test_photo_jpeg(self):
        result = classify("some text", "scan.jpeg")
        self.assertEqual(result["category"], "01_Фото")

    # --- classify() by keywords ---

    def test_inverter_keyword_ua(self):
        result = classify("технічний паспорт інвертор SMA Sunny Boy", "datasheet.pdf")
        self.assertEqual(result["category"], "02_Інвертори")
        self.assertGreaterEqual(result["confidence"], 0.70)

    def test_inverter_keyword_en(self):
        result = classify("Fronius inverter technical data sheet", "fronius.pdf")
        self.assertEqual(result["category"], "02_Інвертори")

    def test_solar_module(self):
        result = classify("JinkoSolar solar module monocrystalline 400W datasheet", "jinko.pdf")
        self.assertEqual(result["category"], "01_Сонячні_модулі")

    def test_battery(self):
        result = classify("BYD battery storage lifepo4 specification", "byd_battery.pdf")
        self.assertEqual(result["category"], "03_Акумулятори")

    def test_consumption(self):
        result = classify("electricity bill рахунок споживання kwh лічильник", "bill.xlsx")
        self.assertEqual(result["category"], "03_Споживання_та_рахунки")

    def test_permit(self):
        result = classify("договір технічні умови підключення до мережі", "contract.docx")
        self.assertEqual(result["category"], "04_ТУ_договори_облік")

    def test_pvsyst(self):
        result = classify("PVsyst simulation annual yield performance ratio", "report.pdf")
        self.assertEqual(result["category"], "pvsyst_reports")

    def test_survey(self):
        result = classify("опитувальний лист вимоги замовника", "questionnaire.docx")
        self.assertEqual(result["category"], "survey_orig")

    # --- confidence formula ---

    def test_confidence_floor_with_text(self):
        result = classify("інвертор fronius", "doc.pdf")
        self.assertGreaterEqual(result["confidence"], 0.80)

    def test_confidence_no_text(self):
        result = classify("", "inverter_doc.pdf")
        # only filename keyword match → 0.65 + 0.1 = 0.75, no text floor
        self.assertGreater(result["confidence"], 0.65)

    def test_unknown_low_confidence(self):
        result = classify("random text no relevant keywords at all", "unknown.txt")
        self.assertEqual(result["category"], "05_Інше")

    def test_empty_input_unknown(self):
        result = classify("", "noext")
        self.assertEqual(result["category"], "05_Інше")
        self.assertLess(result["confidence"], 0.70)

    # --- output contract ---

    def test_result_keys(self):
        result = classify("інвертор", "test.pdf")
        self.assertIn("category", result)
        self.assertIn("confidence", result)
        self.assertIn("reasons", result)
        self.assertIn("document_type_code", result)
        self.assertIsInstance(result["confidence"], float)
        self.assertIsInstance(result["reasons"], list)

    # --- extract_text ---

    def test_extract_text_photo_returns_empty(self):
        self.assertEqual(extract_text("photo.jpg", b"fake bytes"), "")

    def test_extract_text_plain_text(self):
        text = extract_text("file.txt", b"hello world")
        self.assertEqual(text, "hello world")

    def test_extract_text_large_file_returns_empty(self):
        big = b"x" * (51 * 1024 * 1024)
        self.assertEqual(extract_text("big.txt", big), "")
