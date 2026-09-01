import pytest
from datetime import datetime, timezone
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.extraction import (
    ExtractedField,
    ExtractionResult,
    ExtractionStatus,
    ReviewStatus,
)
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal
from app.services import extraction_review


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        all_match_results = db.query(HallTicketMatchResult.id).subquery()
        db.execute(
            delete(HallTicketMatchSignal).where(
                HallTicketMatchSignal.match_result_id.in_(
                    db.query(all_match_results)
                )
            )
        )
        db.execute(delete(HallTicketMatchResult))
        db.execute(delete(ExtractedField))
        db.execute(delete(ExtractionResult))
        db.execute(delete(Document))
        db.commit()
    finally:
        db.close()
    yield


def _create_document(db, status=DocumentStatus.REVIEW_REQUIRED, suffix=""):
    doc = Document(
        original_filename=f"test{suffix}.pdf",
        stored_key=f"test{suffix}.pdf",
        content_type="application/pdf",
        file_size=1024,
        document_type="HALL_TICKET",
        status=status,
    )
    db.add(doc)
    db.flush()
    return doc


def _create_extraction_result(db, document_id, status=ExtractionStatus.REVIEW_REQUIRED):
    er = ExtractionResult(
        document_id=document_id,
        ocr_engine="tesseract5",
        ocr_avg_confidence=85.0,
        processing_time_ms=1500,
        status=status,
    )
    db.add(er)
    db.flush()
    return er


def _create_extracted_field(
    db,
    extraction_result_id,
    field_name="usn",
    extracted_value="1RV21CS001",
    review_status=ReviewStatus.REVIEW_REQUIRED.value,
):
    ef = ExtractedField(
        extraction_result_id=extraction_result_id,
        field_name=field_name,
        extracted_value=extracted_value,
        ocr_confidence=92.0,
        pattern_match=True,
        label_found=True,
        extraction_method="rule_based",
        validation_status="VALID",
        review_status=review_status,
    )
    db.add(ef)
    db.flush()
    return ef


class TestGetReviewData:
    def test_get_review_data_success(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            f1 = _create_extracted_field(db, er.id, "usn", "1RV21CS001")
            f2 = _create_extracted_field(
                db, er.id, "name", "John Doe", ReviewStatus.AUTO_APPROVED.value
            )
            db.commit()

            data = extraction_review.get_review_data(db, doc.id)

            assert data["extraction_result"].id == er.id
            assert len(data["fields"]) == 2
            assert data["progress"]["total_fields"] == 2
            assert data["progress"]["reviewed_count"] == 0
            assert data["progress"]["review_required_count"] == 1
        finally:
            db.close()

    def test_get_review_data_document_not_found(self):
        db = SessionLocal()
        try:
            with pytest.raises(LookupError, match="not found"):
                extraction_review.get_review_data(db, 999999)
        finally:
            db.close()

    def test_get_review_data_no_extraction(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            db.commit()

            with pytest.raises(LookupError, match="No extraction results"):
                extraction_review.get_review_data(db, doc.id)
        finally:
            db.close()

    def test_get_review_data_progress_counts(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id, "usn", "1RV21CS001", ReviewStatus.REVIEWED.value)
            _create_extracted_field(db, er.id, "name", "John Doe", ReviewStatus.REVIEWED.value)
            _create_extracted_field(db, er.id, "exam_date", "2026-09-15", ReviewStatus.REVIEW_REQUIRED.value)
            db.commit()

            data = extraction_review.get_review_data(db, doc.id)

            assert data["progress"]["total_fields"] == 3
            assert data["progress"]["reviewed_count"] == 2
            assert data["progress"]["review_required_count"] == 1
        finally:
            db.close()


class TestCorrectField:
    def test_correct_field_success(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            field = _create_extracted_field(db, er.id, "usn", "1RV21CS0O1")
            db.commit()

            result = extraction_review.correct_field(
                db, doc.id, field.id, "1RV21CS001", ReviewStatus.REVIEWED.value
            )

            assert result.corrected_value == "1RV21CS001"
            assert result.review_status == ReviewStatus.REVIEWED.value
        finally:
            db.close()

    def test_correct_field_save_without_approving(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            field = _create_extracted_field(db, er.id, "usn", "1RV21CS0O1")
            db.commit()

            result = extraction_review.correct_field(
                db, doc.id, field.id, "1RV21CS001", ReviewStatus.REVIEW_REQUIRED.value
            )

            assert result.corrected_value == "1RV21CS001"
            assert result.review_status == ReviewStatus.REVIEW_REQUIRED.value
        finally:
            db.close()

    def test_correct_field_not_found(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            db.commit()

            with pytest.raises(LookupError, match="not found"):
                extraction_review.correct_field(
                    db, doc.id, 999999, "value", ReviewStatus.REVIEWED.value
                )
        finally:
            db.close()

    def test_correct_field_wrong_document(self):
        db = SessionLocal()
        try:
            doc1 = _create_document(db, suffix="1")
            doc2 = _create_document(db, suffix="2")
            er1 = _create_extraction_result(db, doc1.id)
            er2 = _create_extraction_result(db, doc2.id)
            field = _create_extracted_field(db, er1.id, "usn", "1RV21CS001")
            db.commit()

            with pytest.raises(LookupError, match="not found"):
                extraction_review.correct_field(
                    db, doc2.id, field.id, "corrected", ReviewStatus.REVIEWED.value
                )
        finally:
            db.close()

    def test_correct_field_invalid_review_status(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            field = _create_extracted_field(db, er.id, "usn", "1RV21CS001")
            db.commit()

            with pytest.raises(ValueError, match="Invalid review_status"):
                extraction_review.correct_field(
                    db, doc.id, field.id, "corrected", "INVALID_STATUS"
                )
        finally:
            db.close()

    def test_correct_field_no_extraction(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            db.commit()

            with pytest.raises(LookupError, match="No extraction results"):
                extraction_review.correct_field(
                    db, doc.id, 1, "value", ReviewStatus.REVIEWED.value
                )
        finally:
            db.close()

    def test_correct_field_preserves_extracted_value(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            field = _create_extracted_field(db, er.id, "usn", "1RV21CS0O1")
            db.commit()

            extraction_review.correct_field(
                db, doc.id, field.id, "1RV21CS001", ReviewStatus.REVIEWED.value
            )

            db.refresh(field)
            assert field.extracted_value == "1RV21CS0O1"
            assert field.corrected_value == "1RV21CS001"
        finally:
            db.close()


class TestCompleteReview:
    def test_complete_review_success(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            f1 = _create_extracted_field(db, er.id, "usn", "1RV21CS001", ReviewStatus.REVIEWED.value)
            f2 = _create_extracted_field(db, er.id, "name", "John Doe", ReviewStatus.REVIEWED.value)
            db.commit()

            result = extraction_review.complete_review(db, doc.id)

            assert result.status == ExtractionStatus.COMPLETED.value
            assert result.reviewed_at is not None

            db.refresh(doc)
            assert doc.status == DocumentStatus.PROCESSED
        finally:
            db.close()

    def test_complete_review_fail_fields_remaining(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id, "usn", "1RV21CS001", ReviewStatus.REVIEWED.value)
            _create_extracted_field(db, er.id, "name", "John Doe", ReviewStatus.REVIEW_REQUIRED.value)
            db.commit()

            with pytest.raises(ValueError, match="still require review"):
                extraction_review.complete_review(db, doc.id)
        finally:
            db.close()

    def test_complete_review_document_not_found(self):
        db = SessionLocal()
        try:
            with pytest.raises(LookupError, match="not found"):
                extraction_review.complete_review(db, 999999)
        finally:
            db.close()

    def test_complete_review_no_extraction(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            db.commit()

            with pytest.raises(LookupError, match="No extraction results"):
                extraction_review.complete_review(db, doc.id)
        finally:
            db.close()

    def test_complete_review_sets_reviewed_at(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id, "usn", "1RV21CS001", ReviewStatus.REVIEWED.value)
            db.commit()

            before = datetime.now(timezone.utc)
            result = extraction_review.complete_review(db, doc.id)

            assert result.reviewed_at is not None
            reviewed_utc = result.reviewed_at.replace(tzinfo=timezone.utc) if result.reviewed_at.tzinfo is None else result.reviewed_at.astimezone(timezone.utc)
            assert before <= reviewed_utc
        finally:
            db.close()

    def test_complete_review_transitions_document_status(self):
        db = SessionLocal()
        try:
            doc = _create_document(db, DocumentStatus.REVIEW_REQUIRED)
            er = _create_extraction_result(db, doc.id, ExtractionStatus.REVIEW_REQUIRED)
            _create_extracted_field(db, er.id, "usn", "1RV21CS001", ReviewStatus.REVIEWED.value)
            db.commit()

            extraction_review.complete_review(db, doc.id)

            db.refresh(doc)
            assert doc.status == DocumentStatus.PROCESSED

            db.refresh(er)
            assert er.status == ExtractionStatus.COMPLETED.value
        finally:
            db.close()

    def test_complete_review_auto_approved_fields_count(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id, "usn", "1RV21CS001", ReviewStatus.AUTO_APPROVED.value)
            _create_extracted_field(db, er.id, "name", "John Doe", ReviewStatus.AUTO_APPROVED.value)
            db.commit()

            result = extraction_review.complete_review(db, doc.id)
            assert result.status == ExtractionStatus.COMPLETED.value
        finally:
            db.close()


class TestCorrectionFlow:
    def test_end_to_end_review_flow(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            f1 = _create_extracted_field(db, er.id, "usn", "1RV21CS0O1")
            f2 = _create_extracted_field(db, er.id, "name", "Jon Doe")
            db.commit()

            data = extraction_review.get_review_data(db, doc.id)
            assert data["progress"]["review_required_count"] == 2

            extraction_review.correct_field(db, doc.id, f1.id, "1RV21CS001")

            data = extraction_review.get_review_data(db, doc.id)
            assert data["progress"]["review_required_count"] == 1

            extraction_review.correct_field(db, doc.id, f2.id, "John Doe")

            data = extraction_review.get_review_data(db, doc.id)
            assert data["progress"]["review_required_count"] == 0
            assert data["progress"]["reviewed_count"] == 2

            result = extraction_review.complete_review(db, doc.id)
            assert result.status == ExtractionStatus.COMPLETED.value

            db.refresh(doc)
            assert doc.status == DocumentStatus.PROCESSED

            db.refresh(f1)
            assert f1.corrected_value == "1RV21CS001"
            assert f1.extracted_value == "1RV21CS0O1"

            db.refresh(f2)
            assert f2.corrected_value == "John Doe"
            assert f2.extracted_value == "Jon Doe"
        finally:
            db.close()

    def test_correction_then_match_uses_corrected_value(self):
        from app.services.hall_ticket_matching import _get_extracted_value

        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            field = _create_extracted_field(db, er.id, "usn", "1RV21CS0O1")
            db.commit()

            fields = [field]
            value = _get_extracted_value(fields, "usn")
            assert value == "1RV21CS0O1"

            extraction_review.correct_field(
                db, doc.id, field.id, "1RV21CS001", ReviewStatus.REVIEWED.value
            )

            db.refresh(field)
            fields = [field]
            value = _get_extracted_value(fields, "usn")
            assert value == "1RV21CS001"
        finally:
            db.close()


class TestSecurityBoundary:
    def test_original_extracted_value_preserved(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            field = _create_extracted_field(
                db, er.id, "usn", "ORIGINAL_VALUE"
            )
            db.commit()

            extraction_review.correct_field(
                db, doc.id, field.id, "CORRECTED_VALUE"
            )

            db.refresh(field)
            assert field.extracted_value == "ORIGINAL_VALUE"
            assert field.corrected_value == "CORRECTED_VALUE"
        finally:
            db.close()

    def test_no_new_records_created_by_review(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            field = _create_extracted_field(db, er.id, "usn", "1RV21CS001")
            db.commit()

            initial_field_count = db.query(ExtractedField).count()
            initial_result_count = db.query(ExtractionResult).count()

            extraction_review.correct_field(
                db, doc.id, field.id, "1RV21CS001"
            )
            extraction_review.complete_review(db, doc.id)

            assert db.query(ExtractedField).count() == initial_field_count
            assert db.query(ExtractionResult).count() == initial_result_count
        finally:
            db.close()

    def test_review_does_not_mutate_student_data(self):
        from app.models.student import Student

        db = SessionLocal()
        try:
            student = Student(
                usn="REV_UNIQUE_001",
                name="Test Student",
                is_active=True,
            )
            db.add(student)
            db.flush()

            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            field = _create_extracted_field(db, er.id, "usn", "WRONG_USN")
            db.commit()

            student_name_before = student.name
            student_usn_before = student.usn

            extraction_review.correct_field(
                db, doc.id, field.id, "1RV21CS001"
            )

            db.refresh(student)
            assert student.name == student_name_before
            assert student.usn == student_usn_before
        finally:
            db.close()
