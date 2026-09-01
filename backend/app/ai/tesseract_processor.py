import logging
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.ai.base import DocumentProcessor, OCRResult, OCRWord
from app.ai.preprocessing import preprocess_image
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class TesseractDocumentProcessor(DocumentProcessor):
    def __init__(self) -> None:
        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    def is_available(self) -> bool:
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def process_image(self, image_path: str, page: int = 0) -> OCRResult:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        processed = preprocess_image(img)
        pil_image = Image.fromarray(processed)

        return self._run_ocr(pil_image, page)

    def process_pdf(self, pdf_path: str) -> list[OCRResult]:
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise RuntimeError("pdf2image not installed. Install poppler-utils.")

        kwargs = {}
        if settings.POPPLER_PATH:
            kwargs["poppler_path"] = settings.POPPLER_PATH

        pages = convert_from_path(pdf_path, dpi=300, **kwargs)
        results = []

        for i, page_img in enumerate(pages):
            img_array = np.array(page_img)
            if len(img_array.shape) == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

            processed = preprocess_image(img_array)
            pil_image = Image.fromarray(processed)
            result = self._run_ocr(pil_image, page=i)
            results.append(result)

        return results

    def _run_ocr(self, pil_image: Image.Image, page: int = 0) -> OCRResult:
        config = f"--psm 6 --oem 1 -l {settings.OCR_LANGUAGE}"

        data = pytesseract.image_to_data(pil_image, config=config, output_type=pytesseract.Output.DICT)

        words = []
        text_parts = []
        total_conf = 0.0
        conf_count = 0

        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = data["text"][i].strip()
            if not text:
                continue

            conf = float(data["conf"][i])
            if conf < 0:
                continue

            word = OCRWord(
                text=text,
                confidence=conf,
                x=data["left"][i],
                y=data["top"][i],
                width=data["width"][i],
                height=data["height"][i],
                page=page,
            )
            words.append(word)
            text_parts.append(text)
            total_conf += conf
            conf_count += 1

        full_text = pytesseract.image_to_string(pil_image, config=config)
        avg_conf = total_conf / conf_count if conf_count > 0 else 0.0

        return OCRResult(
            text=full_text.strip(),
            words=words,
            page=page,
            engine="tesseract5",
            config=config,
            avg_confidence=avg_conf,
        )
