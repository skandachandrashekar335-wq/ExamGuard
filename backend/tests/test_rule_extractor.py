import pytest

from app.ai.base import OCRResult, OCRWord
from app.ai.rule_extractor import RuleBasedFieldExtractor


class TestRuleBasedFieldExtractor:
    def setup_method(self):
        self.extractor = RuleBasedFieldExtractor()

    def test_extract_usn_labeled(self):
        ocr_result = OCRResult(
            text="University Seat Number: 1RV21CS001",
            words=[
                OCRWord(text="University", confidence=95.0, x=0, y=0, width=100, height=20, page=0),
                OCRWord(text="Seat", confidence=95.0, x=100, y=0, width=50, height=20, page=0),
                OCRWord(text="Number:", confidence=95.0, x=150, y=0, width=80, height=20, page=0),
                OCRWord(text="1RV21CS001", confidence=98.0, x=230, y=0, width=120, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )

        output = self.extractor.extract([ocr_result])

        usn_field = next((f for f in output.fields if f.field_name == "usn"), None)
        assert usn_field is not None
        assert usn_field.extracted_value == "1RV21CS001"
        assert usn_field.label_found is True
        assert usn_field.extraction_method == "labeled_regex"

    def test_extract_name_labeled(self):
        ocr_result = OCRResult(
            text="Student Name: John Doe",
            words=[
                OCRWord(text="Student", confidence=95.0, x=0, y=0, width=80, height=20, page=0),
                OCRWord(text="Name:", confidence=95.0, x=80, y=0, width=60, height=20, page=0),
                OCRWord(text="John", confidence=98.0, x=140, y=0, width=50, height=20, page=0),
                OCRWord(text="Doe", confidence=98.0, x=190, y=0, width=40, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )

        output = self.extractor.extract([ocr_result])

        name_field = next((f for f in output.fields if f.field_name == "name"), None)
        assert name_field is not None
        assert name_field.extracted_value == "John Doe"
        assert name_field.label_found is True

    def test_extract_exam_date(self):
        ocr_result = OCRResult(
            text="Exam Date: 15/03/2026",
            words=[
                OCRWord(text="Exam", confidence=95.0, x=0, y=0, width=50, height=20, page=0),
                OCRWord(text="Date:", confidence=95.0, x=50, y=0, width=60, height=20, page=0),
                OCRWord(text="15/03/2026", confidence=98.0, x=110, y=0, width=100, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )

        output = self.extractor.extract([ocr_result])

        date_field = next((f for f in output.fields if f.field_name == "exam_date"), None)
        assert date_field is not None
        assert date_field.extracted_value == "2026-03-15"
        assert date_field.pattern_match is True

    def test_extract_start_time(self):
        ocr_result = OCRResult(
            text="Start Time: 10:30 AM",
            words=[
                OCRWord(text="Start", confidence=95.0, x=0, y=0, width=60, height=20, page=0),
                OCRWord(text="Time:", confidence=95.0, x=60, y=0, width=60, height=20, page=0),
                OCRWord(text="10:30", confidence=98.0, x=120, y=0, width=60, height=20, page=0),
                OCRWord(text="AM", confidence=98.0, x=180, y=0, width=30, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )

        output = self.extractor.extract([ocr_result])

        time_field = next((f for f in output.fields if f.field_name == "start_time"), None)
        assert time_field is not None
        assert time_field.extracted_value == "10:30"
        assert time_field.pattern_match is True

    def test_extract_exam_hall(self):
        ocr_result = OCRResult(
            text="Hall: Room 301",
            words=[
                OCRWord(text="Hall:", confidence=95.0, x=0, y=0, width=50, height=20, page=0),
                OCRWord(text="Room", confidence=98.0, x=50, y=0, width=50, height=20, page=0),
                OCRWord(text="301", confidence=98.0, x=100, y=0, width=40, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )

        output = self.extractor.extract([ocr_result])

        hall_field = next((f for f in output.fields if f.field_name == "exam_hall"), None)
        assert hall_field is not None
        assert "301" in (hall_field.extracted_value or "")

    def test_missing_field_not_found(self):
        ocr_result = OCRResult(
            text="Random text without labels",
            words=[
                OCRWord(text="Random", confidence=90.0, x=0, y=0, width=80, height=20, page=0),
                OCRWord(text="text", confidence=90.0, x=80, y=0, width=50, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )

        output = self.extractor.extract([ocr_result])

        usn_field = next((f for f in output.fields if f.field_name == "usn"), None)
        assert usn_field is not None
        assert usn_field.extracted_value is None
        assert usn_field.label_found is False

    def test_usn_normalization(self):
        ocr_result = OCRResult(
            text="USN: 1rv21cs001",
            words=[
                OCRWord(text="USN:", confidence=95.0, x=0, y=0, width=50, height=20, page=0),
                OCRWord(text="1rv21cs001", confidence=98.0, x=50, y=0, width=100, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )

        output = self.extractor.extract([ocr_result])

        usn_field = next((f for f in output.fields if f.field_name == "usn"), None)
        assert usn_field is not None
        assert usn_field.extracted_value == "1RV21CS001"

    def test_name_normalization(self):
        ocr_result = OCRResult(
            text="Name:   john   doe  ",
            words=[
                OCRWord(text="Name:", confidence=95.0, x=0, y=0, width=60, height=20, page=0),
                OCRWord(text="john", confidence=98.0, x=60, y=0, width=50, height=20, page=0),
                OCRWord(text="doe", confidence=98.0, x=110, y=0, width=40, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )

        output = self.extractor.extract([ocr_result])

        name_field = next((f for f in output.fields if f.field_name == "name"), None)
        assert name_field is not None
        assert name_field.extracted_value == "john doe"

    def test_multiple_pages(self):
        page1 = OCRResult(
            text="Name: John Doe",
            words=[
                OCRWord(text="Name:", confidence=95.0, x=0, y=0, width=60, height=20, page=0),
                OCRWord(text="John", confidence=98.0, x=60, y=0, width=50, height=20, page=0),
                OCRWord(text="Doe", confidence=98.0, x=110, y=0, width=40, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )
        page2 = OCRResult(
            text="USN: 1RV21CS001",
            words=[
                OCRWord(text="USN:", confidence=95.0, x=0, y=0, width=50, height=20, page=1),
                OCRWord(text="1RV21CS001", confidence=98.0, x=50, y=0, width=100, height=20, page=1),
            ],
            page=1,
            engine="tesseract5",
        )

        output = self.extractor.extract([page1, page2])

        name_field = next((f for f in output.fields if f.field_name == "name"), None)
        usn_field = next((f for f in output.fields if f.field_name == "usn"), None)
        assert name_field is not None
        assert name_field.extracted_value == "John Doe"
        assert usn_field is not None
        assert usn_field.extracted_value == "1RV21CS001"

    def test_empty_ocr_result(self):
        ocr_result = OCRResult(text="", words=[], page=0, engine="tesseract5")

        output = self.extractor.extract([ocr_result])

        assert len(output.fields) == len(["name", "usn", "exam_name", "subject", "exam_date",
                                          "start_time", "end_time", "semester", "department", "exam_hall"])
        for field in output.fields:
            assert field.extracted_value is None
            assert field.label_found is False

    def test_raw_text_preserved(self):
        ocr_result = OCRResult(
            text="Full OCR text here",
            words=[],
            page=0,
            engine="tesseract5",
        )

        output = self.extractor.extract([ocr_result])

        assert output.raw_text == "Full OCR text here"


class TestFieldLevelConfidence:
    def setup_method(self):
        self.extractor = RuleBasedFieldExtractor()

    def test_labeled_field_gets_confidence_from_source_words(self):
        ocr_result = OCRResult(
            text="Name: John Doe",
            words=[
                OCRWord(text="Name:", confidence=95.0, x=0, y=0, width=60, height=20, page=0),
                OCRWord(text="John", confidence=98.0, x=60, y=0, width=50, height=20, page=0),
                OCRWord(text="Doe", confidence=97.0, x=110, y=0, width=40, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )
        output = self.extractor.extract([ocr_result])
        name_field = next(f for f in output.fields if f.field_name == "name")
        assert name_field.ocr_confidence is not None
        assert name_field.ocr_confidence == pytest.approx((98.0 + 97.0) / 2)

    def test_multiple_source_words_averaged_correctly(self):
        ocr_result = OCRResult(
            text="Subject: Operating Systems Design",
            words=[
                OCRWord(text="Subject:", confidence=90.0, x=0, y=0, width=80, height=20, page=0),
                OCRWord(text="Operating", confidence=92.0, x=80, y=0, width=100, height=20, page=0),
                OCRWord(text="Systems", confidence=94.0, x=180, y=0, width=80, height=20, page=0),
                OCRWord(text="Design", confidence=96.0, x=260, y=0, width=70, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )
        output = self.extractor.extract([ocr_result])
        subject_field = next(f for f in output.fields if f.field_name == "subject")
        assert subject_field.ocr_confidence is not None
        assert subject_field.ocr_confidence == pytest.approx((92.0 + 94.0 + 96.0) / 3)

    def test_one_word_field_gets_that_words_confidence(self):
        ocr_result = OCRResult(
            text="Semester: 5",
            words=[
                OCRWord(text="Semester:", confidence=93.0, x=0, y=0, width=90, height=20, page=0),
                OCRWord(text="5", confidence=99.0, x=90, y=0, width=15, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )
        output = self.extractor.extract([ocr_result])
        sem_field = next(f for f in output.fields if f.field_name == "semester")
        assert sem_field.ocr_confidence is not None
        assert sem_field.ocr_confidence == pytest.approx(99.0)

    def test_confidence_none_when_no_matching_words(self):
        ocr_result = OCRResult(
            text="Name: Unknown",
            words=[],
            page=0,
            engine="tesseract5",
        )
        output = self.extractor.extract([ocr_result])
        name_field = next(f for f in output.fields if f.field_name == "name")
        assert name_field.ocr_confidence is None

    def test_confidence_none_when_field_not_found(self):
        ocr_result = OCRResult(
            text="Random text",
            words=[
                OCRWord(text="Random", confidence=90.0, x=0, y=0, width=70, height=20, page=0),
                OCRWord(text="text", confidence=90.0, x=70, y=0, width=50, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )
        output = self.extractor.extract([ocr_result])
        usn_field = next(f for f in output.fields if f.field_name == "usn")
        assert usn_field.ocr_confidence is None

    def test_bounding_boxes_preserved(self):
        ocr_result = OCRResult(
            text="USN: 1RV21CS001",
            words=[
                OCRWord(text="USN:", confidence=95.0, x=10, y=20, width=45, height=18, page=0),
                OCRWord(text="1RV21CS001", confidence=98.0, x=60, y=20, width=110, height=18, page=0),
            ],
            page=0,
            engine="tesseract5",
        )
        output = self.extractor.extract([ocr_result])
        usn_field = next(f for f in output.fields if f.field_name == "usn")
        assert usn_field.ocr_confidence is not None
        assert usn_field.extracted_value == "1RV21CS001"
        assert usn_field.label_found is True

    def test_extraction_values_unchanged(self):
        ocr_result = OCRResult(
            text="Name: Jane Smith\nUSN: 4MW21CS099\nDate: 20/12/2026",
            words=[
                OCRWord(text="Name:", confidence=95.0, x=0, y=0, width=60, height=20, page=0),
                OCRWord(text="Jane", confidence=97.0, x=60, y=0, width=50, height=20, page=0),
                OCRWord(text="Smith", confidence=97.0, x=110, y=0, width=60, height=20, page=0),
                OCRWord(text="USN:", confidence=95.0, x=0, y=40, width=45, height=20, page=0),
                OCRWord(text="4MW21CS099", confidence=98.0, x=50, y=40, width=110, height=20, page=0),
                OCRWord(text="Date:", confidence=95.0, x=0, y=80, width=50, height=20, page=0),
                OCRWord(text="20/12/2026", confidence=96.0, x=55, y=80, width=100, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
        )
        output = self.extractor.extract([ocr_result])
        name_f = next(f for f in output.fields if f.field_name == "name")
        usn_f = next(f for f in output.fields if f.field_name == "usn")
        date_f = next(f for f in output.fields if f.field_name == "exam_date")

        assert name_f.extracted_value == "Jane Smith"
        assert usn_f.extracted_value == "4MW21CS099"
        assert date_f.extracted_value == "2026-12-20"

        assert name_f.ocr_confidence == pytest.approx((97.0 + 97.0) / 2)
        assert usn_f.ocr_confidence == pytest.approx(98.0)
        assert date_f.ocr_confidence == pytest.approx(96.0)
