import re
from datetime import datetime

from app.ai.base import OCRResult, OCRWord
from app.ai.extraction_base import ExtractionOutput, ExtractedFieldData, FieldExtractor
from app.core.config import get_settings

settings = get_settings()

FIELD_LABELS = {
    "name": ["name", "student name", "candidate name", "student's name"],
    "usn": ["usn", "university seat number", "seat number", "student id", "id number"],
    "exam_name": ["exam", "examination", "exam name", "examination name", "exam type"],
    "subject": ["subject", "paper", "course", "subject name"],
    "exam_date": ["date", "exam date", "examination date", "date of exam"],
    "start_time": ["start time", "beginning time", "from time", "time from"],
    "end_time": ["end time", "closing time", "to time", "time to"],
    "semester": ["semester", "sem", "term"],
    "department": ["department", "branch", "dept", "discipline"],
    "exam_hall": ["hall", "room", "venue", "exam hall", "classroom", "center"],
}

DATE_PATTERNS = [
    (r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", "%d/%m/%Y"),
    (r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", "%d-%m-%Y"),
    (r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", "%Y-%m-%d"),
    (r"\d{1,2}\s+\w+\s+\d{4}", None),
]

TIME_PATTERNS = [
    r"\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?",
    r"\d{1,2}\s*(?:AM|PM|am|pm)",
]


class RuleBasedFieldExtractor(FieldExtractor):
    def extract(self, ocr_results: list[OCRResult]) -> ExtractionOutput:
        all_text = "\n".join(r.text for r in ocr_results)
        all_words = []
        for r in ocr_results:
            all_words.extend(r.words)

        fields = []

        for field_name, labels in FIELD_LABELS.items():
            field_data = self._extract_labeled_field(field_name, labels, all_text, all_words)
            fields.append(field_data)

        usn_field = next((f for f in fields if f.field_name == "usn"), None)
        if usn_field and usn_field.extracted_value:
            usn_field.extracted_value = self._normalize_usn(usn_field.extracted_value)
            if settings.USN_PATTERN:
                usn_field.pattern_match = bool(re.match(settings.USN_PATTERN, usn_field.extracted_value))

        name_field = next((f for f in fields if f.field_name == "name"), None)
        if name_field and name_field.extracted_value:
            name_field.extracted_value = self._normalize_name(name_field.extracted_value)

        date_fields = [f for f in fields if "date" in f.field_name]
        for df in date_fields:
            if df.extracted_value:
                normalized = self._parse_date(df.extracted_value)
                if normalized:
                    df.extracted_value = normalized
                    df.pattern_match = True

        time_fields = [f for f in fields if "time" in f.field_name]
        for tf in time_fields:
            if tf.extracted_value:
                normalized = self._parse_time(tf.extracted_value)
                if normalized:
                    tf.extracted_value = normalized
                    tf.pattern_match = True

        return ExtractionOutput(fields=fields, raw_text=all_text)

    def _extract_labeled_field(
        self,
        field_name: str,
        labels: list[str],
        full_text: str,
        words: list[OCRWord],
    ) -> ExtractedFieldData:
        text_lower = full_text.lower()

        for label in labels:
            pattern = re.compile(
                rf"{re.escape(label)}\s*[:.\-=]\s*(.+?)(?:\n|$)",
                re.IGNORECASE,
            )
            match = pattern.search(full_text)
            if match:
                value = match.group(1).strip()
                value = re.sub(r"\s+", " ", value)
                return ExtractedFieldData(
                    field_name=field_name,
                    extracted_value=value,
                    label_found=True,
                    extraction_method="labeled_regex",
                    ocr_confidence=self._confidence_for_value(value, words),
                )

        for label in labels:
            for i, word in enumerate(words):
                if word.text.lower().rstrip(":.") == label.lower():
                    value_words = self._collect_following_words(words, i + 1, max_words=8)
                    if value_words:
                        value = " ".join(w.text for w in value_words)
                        return ExtractedFieldData(
                            field_name=field_name,
                            extracted_value=value,
                            label_found=True,
                            extraction_method="labeled_positional",
                            ocr_confidence=sum(w.confidence for w in value_words) / len(value_words),
                        )

        return ExtractedFieldData(
            field_name=field_name,
            label_found=False,
            extraction_method="not_found",
        )

    def _collect_following_words(
        self, words: list[OCRWord], start: int, max_words: int = 8
    ) -> list[OCRWord]:
        result = []
        last_y = None
        for i in range(start, min(start + max_words * 3, len(words))):
            w = words[i]
            if last_y is not None and abs(w.y - last_y) > 20:
                break
            if w.text.strip():
                result.append(w)
                last_y = w.y
                if len(result) >= max_words:
                    break
        return result

    def _confidence_for_value(
        self, value: str, words: list[OCRWord]
    ) -> float | None:
        if not value or not words:
            return None

        value_tokens = value.lower().split()
        if not value_tokens:
            return None

        matched_words: list[OCRWord] = []
        used_indices: set[int] = set()

        for token in value_tokens:
            clean_token = re.sub(r"[^a-z0-9]", "", token)
            if not clean_token:
                continue
            for i, w in enumerate(words):
                if i in used_indices:
                    continue
                clean_word = re.sub(r"[^a-zA-Z0-9]", "", w.text).lower()
                if clean_word == clean_token:
                    matched_words.append(w)
                    used_indices.add(i)
                    break

        if not matched_words:
            return None

        return sum(w.confidence for w in matched_words) / len(matched_words)

    def _normalize_usn(self, value: str) -> str:
        value = value.strip()
        value = re.sub(r"\s+", "", value)
        value = value.upper()
        return value

    def _normalize_name(self, value: str) -> str:
        value = value.strip()
        value = re.sub(r"\s+", " ", value)
        value = re.sub(r"[^a-zA-Z\s.\-']", "", value)
        return value.strip()

    def _parse_date(self, value: str) -> str | None:
        formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y"]
        for fmt in formats:
            try:
                dt = datetime.strptime(value.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        month_pattern = r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})"
        match = re.match(month_pattern, value.strip(), re.IGNORECASE)
        if match:
            try:
                dt = datetime.strptime(match.group(0), "%d %B %Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return None

    def _parse_time(self, value: str) -> str | None:
        value = value.strip()
        patterns = [
            (r"(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)", "%I:%M%p"),
            (r"(\d{1,2}):(\d{2})", "%H:%M"),
            (r"(\d{1,2})\s*(AM|PM|am|pm)", "%I%p"),
        ]
        for pattern, fmt in patterns:
            match = re.match(pattern, value)
            if match:
                try:
                    time_str = match.group(0).replace(" ", "")
                    dt = datetime.strptime(time_str.upper(), fmt)
                    return dt.strftime("%H:%M")
                except ValueError:
                    continue
        return None
