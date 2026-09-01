from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.ai.base import OCRResult


@dataclass
class ExtractedFieldData:
    field_name: str
    extracted_value: str | None = None
    ocr_confidence: float | None = None
    pattern_match: bool | None = None
    label_found: bool | None = None
    database_match: bool | None = None
    extraction_method: str | None = None
    validation_status: str = "UNCERTAIN"


@dataclass
class ExtractionOutput:
    fields: list[ExtractedFieldData] = field(default_factory=list)
    raw_text: str = ""


class FieldExtractor(ABC):
    @abstractmethod
    def extract(self, ocr_results: list[OCRResult]) -> ExtractionOutput:
        """Extract structured fields from OCR results."""
