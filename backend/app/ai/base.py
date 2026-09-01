from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class OCRWord:
    text: str
    confidence: float
    x: int
    y: int
    width: int
    height: int
    page: int


@dataclass
class OCRResult:
    text: str
    words: list[OCRWord] = field(default_factory=list)
    page: int = 0
    engine: str = ""
    config: str = ""
    avg_confidence: float = 0.0


class DocumentProcessor(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the processor is properly configured."""

    @abstractmethod
    def process_image(self, image_path: str, page: int = 0) -> OCRResult:
        """Process a single image file."""

    @abstractmethod
    def process_pdf(self, pdf_path: str) -> list[OCRResult]:
        """Process a PDF file, returning one OCRResult per page."""
