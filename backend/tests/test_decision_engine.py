"""Phase 8.5 — Threshold + Decision Integration.

Tests the enhanced decision engine with configurable thresholds, boundary
testing, missing evidence handling, provider failure → decision mapping,
audit metadata, and security invariants.
"""

import pytest
from unittest.mock import patch

from app.core.config import Settings
from app.models.identity_verification import IdentityVerificationEvidence
from app.services.identity_verification_decision import (
    DecisionResult,
    evaluate_evidence,
    evaluate_evidence_detailed,
)


def _evidence(signal_type: str, signal_value: str, confidence: float | None = None, provider_name: str | None = None) -> IdentityVerificationEvidence:
    return IdentityVerificationEvidence(
        signal_type=signal_type,
        signal_value=signal_value,
        confidence=confidence,
        provider_name=provider_name,
    )


def _similarity(score: float, provider_name: str | None = None) -> IdentityVerificationEvidence:
    return _evidence("similarity_score", str(score), confidence=score, provider_name=provider_name)


def _liveness(value: str) -> IdentityVerificationEvidence:
    return _evidence("liveness", value)


def _quality(value: str) -> IdentityVerificationEvidence:
    return _evidence("image_quality", value)


class TestDecisionBoundary:
    """Boundary testing at exact threshold, just above, just below."""

    def test_exact_threshold_is_match(self):
        decision, _ = evaluate_evidence([_similarity(0.85)])
        assert decision == "MATCH"

    def test_one_above_threshold(self):
        decision, _ = evaluate_evidence([_similarity(0.851)])
        assert decision == "MATCH"

    def test_just_below_threshold_is_near_zone(self):
        decision, _ = evaluate_evidence([_similarity(0.84)])
        assert decision == "INCONCLUSIVE"

    def test_threshold_zero_point_eight_five(self):
        decision, _ = evaluate_evidence([_similarity(0.85)])
        assert decision == "MATCH"

    def test_threshold_zero_point_eight_six(self):
        decision, _ = evaluate_evidence([_similarity(0.86)])
        assert decision == "MATCH"

    def test_threshold_zero_point_eight_four(self):
        decision, _ = evaluate_evidence([_similarity(0.84)])
        assert decision == "INCONCLUSIVE"

    def test_zero_score_is_no_match(self):
        decision, _ = evaluate_evidence([_similarity(0.0)])
        assert decision == "NO_MATCH"

    def test_one_score_is_match(self):
        decision, _ = evaluate_evidence([_similarity(1.0)])
        assert decision == "MATCH"

    def test_half_threshold_is_no_match(self):
        decision, _ = evaluate_evidence([_similarity(0.425)])
        assert decision == "NO_MATCH"

    def test_boundary_zero_is_no_match(self):
        decision, _ = evaluate_evidence([_similarity(0.0)])
        assert decision == "NO_MATCH"

    def test_boundary_one_is_match(self):
        decision, _ = evaluate_evidence([_similarity(1.0)])
        assert decision == "MATCH"


class TestNearThresholdZone:
    """Test the near-threshold zone logic with configurable factor."""

    def test_near_zone_default_factor(self):
        # Default: threshold=0.85, factor=0.7 → near_threshold=0.595
        # 0.65 is in near zone [0.595, 0.85)
        decision, _ = evaluate_evidence([_similarity(0.65)])
        assert decision == "INCONCLUSIVE"

    def test_below_near_zone_is_no_match(self):
        # 0.50 < 0.595 → NO_MATCH
        decision, _ = evaluate_evidence([_similarity(0.50)])
        assert decision == "NO_MATCH"

    def test_at_near_zone_lower_bound(self):
        # 0.595 = 0.85 * 0.7 → exact boundary of near zone
        decision, _ = evaluate_evidence([_similarity(0.595)])
        assert decision == "INCONCLUSIVE"

    def test_just_below_near_zone(self):
        # 0.594 < 0.595 → NO_MATCH
        decision, _ = evaluate_evidence([_similarity(0.594)])
        assert decision == "NO_MATCH"

    def test_high_similarity_near_zone(self):
        # 0.84 is in near zone [0.595, 0.85)
        decision, _ = evaluate_evidence([_similarity(0.84)])
        assert decision == "INCONCLUSIVE"

    @patch("app.services.identity_verification_decision.get_settings")
    def test_wider_near_zone_with_higher_factor(self, mock_settings):
        mock_settings.return_value = Settings(
            IDENTITY_VERIFICATION_MATCH_THRESHOLD=0.85,
            IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR=0.9,
        )
        # near_threshold = 0.85 * 0.9 = 0.765
        decision, _ = evaluate_evidence([_similarity(0.77)])
        assert decision == "INCONCLUSIVE"

    @patch("app.services.identity_verification_decision.get_settings")
    def test_narrower_near_zone_with_lower_factor(self, mock_settings):
        mock_settings.return_value = Settings(
            IDENTITY_VERIFICATION_MATCH_THRESHOLD=0.85,
            IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR=0.5,
        )
        # near_threshold = 0.85 * 0.5 = 0.425
        decision, _ = evaluate_evidence([_similarity(0.50)])
        assert decision == "INCONCLUSIVE"

    @patch("app.services.identity_verification_decision.get_settings")
    def test_near_threshold_factor_one(self, mock_settings):
        mock_settings.return_value = Settings(
            IDENTITY_VERIFICATION_MATCH_THRESHOLD=0.85,
            IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR=1.0,
        )
        # near_threshold = 0.85 * 1.0 = 0.85 → same as threshold
        decision, _ = evaluate_evidence([_similarity(0.84)])
        assert decision == "NO_MATCH"

    @patch("app.services.identity_verification_decision.get_settings")
    def test_average_similarity_used_in_near_zone(self, mock_settings):
        mock_settings.return_value = Settings(
            IDENTITY_VERIFICATION_MATCH_THRESHOLD=0.85,
            IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR=0.7,
        )
        # Average of 0.50 and 0.69 = 0.595, which is exactly near_threshold
        evidence = [_similarity(0.50), _similarity(0.69)]
        decision, _ = evaluate_evidence(evidence)
        assert decision == "INCONCLUSIVE"


class TestMissingEvidence:
    """Test handling of missing evidence signals."""

    def test_no_evidence_returns_inconclusive(self):
        decision, reasoning = evaluate_evidence([])
        assert decision == "INCONCLUSIVE"
        assert "No evidence" in reasoning

    def test_similarity_only(self):
        decision, _ = evaluate_evidence([_similarity(0.90)])
        assert decision == "MATCH"

    def test_liveness_only_pass(self):
        decision, reasoning = evaluate_evidence([_liveness("PASS")])
        assert decision == "INCONCLUSIVE"
        assert "no similarity" in reasoning.lower() or "insufficient" in reasoning.lower()

    def test_liveness_only_fail(self):
        decision, _ = evaluate_evidence([_liveness("FAIL")])
        assert decision == "NO_MATCH"

    def test_quality_only(self):
        decision, reasoning = evaluate_evidence([_quality("POOR")])
        assert decision == "INCONCLUSIVE"

    def test_similarity_and_liveness_pass(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _liveness("PASS")])
        assert decision == "MATCH"

    def test_similarity_and_liveness_fail(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _liveness("FAIL")])
        assert decision == "NO_MATCH"

    def test_similarity_and_quality_poor(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _quality("POOR")])
        assert decision == "INCONCLUSIVE"

    def test_all_signals_available(self):
        decision, _ = evaluate_evidence([
            _similarity(0.90), _liveness("PASS"), _quality("GOOD")
        ])
        assert decision == "MATCH"

    def test_all_signals_available_poor_quality(self):
        decision, _ = evaluate_evidence([
            _similarity(0.90), _liveness("PASS"), _quality("POOR")
        ])
        assert decision == "INCONCLUSIVE"


class TestLivenessPolicy:
    """Test liveness failure handling across different similarity scores."""

    def test_liveness_fail_overrides_high_similarity(self):
        decision, _ = evaluate_evidence([_similarity(0.99), _liveness("FAIL")])
        assert decision == "NO_MATCH"

    def test_liveness_fail_overrides_medium_similarity(self):
        decision, _ = evaluate_evidence([_similarity(0.70), _liveness("FAIL")])
        assert decision == "NO_MATCH"

    def test_liveness_fail_overrides_low_similarity(self):
        decision, _ = evaluate_evidence([_similarity(0.30), _liveness("FAIL")])
        assert decision == "NO_MATCH"

    def test_liveness_pass_with_high_similarity(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _liveness("PASS")])
        assert decision == "MATCH"

    def test_liveness_spoof_detected(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _liveness("spoof_detected")])
        assert decision == "NO_MATCH"

    def test_liveness_lowercase_fail(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _liveness("fail")])
        assert decision == "NO_MATCH"

    def test_liveness_false_value(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _liveness("false")])
        assert decision == "NO_MATCH"


class TestProviderFailureMapping:
    """Test how provider failures map to decisions."""

    def test_provider_name_recorded_in_metadata(self):
        result = evaluate_evidence_detailed([
            _similarity(0.90, provider_name="uniface"),
            _liveness("PASS"),
        ])
        assert "uniface" in result.metadata["providers_used"]

    def test_multiple_providers_in_metadata(self):
        result = evaluate_evidence_detailed([
            _similarity(0.90, provider_name="uniface"),
            _similarity(0.88, provider_name="fallback"),
        ])
        assert set(result.metadata["providers_used"]) == {"uniface", "fallback"}

    def test_provider_failure_not_silently_converted(self):
        # A provider failure (no similarity score) should not be NO_MATCH
        decision, reasoning = evaluate_evidence([_liveness("PASS")])
        assert decision == "INCONCLUSIVE"
        assert "insufficient" in reasoning.lower() or "no similarity" in reasoning.lower()


class TestQualityPolicy:
    """Test quality issue handling."""

    def test_poor_quality_with_high_similarity(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _quality("POOR")])
        assert decision == "INCONCLUSIVE"

    def test_poor_quality_with_low_similarity(self):
        decision, _ = evaluate_evidence([_similarity(0.40), _quality("POOR")])
        assert decision == "NO_MATCH"

    def test_good_quality_with_high_similarity(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _quality("GOOD")])
        assert decision == "MATCH"

    def test_unacceptable_quality(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _quality("UNACCEPTABLE")])
        assert decision == "INCONCLUSIVE"

    def test_low_quality(self):
        decision, _ = evaluate_evidence([_similarity(0.90), _quality("LOW")])
        assert decision == "INCONCLUSIVE"


class TestDecisionMetadata:
    """Test that decision results include audit-friendly metadata."""

    def test_metadata_includes_threshold(self):
        result = evaluate_evidence_detailed([_similarity(0.90)])
        assert result.metadata["threshold"] == 0.85

    def test_metadata_includes_near_threshold(self):
        result = evaluate_evidence_detailed([_similarity(0.90)])
        assert result.metadata["near_threshold"] == pytest.approx(0.595)

    def test_metadata_includes_policy_version(self):
        result = evaluate_evidence_detailed([_similarity(0.90)])
        assert result.policy_version == "1.0"

    def test_metadata_includes_similarity_count(self):
        result = evaluate_evidence_detailed([_similarity(0.90), _similarity(0.88)])
        assert result.metadata["similarity_scores_count"] == 2

    def test_metadata_includes_liveness_count(self):
        result = evaluate_evidence_detailed([_similarity(0.90), _liveness("PASS")])
        assert result.metadata["liveness_signals_count"] == 1

    def test_metadata_includes_max_similarity(self):
        result = evaluate_evidence_detailed([_similarity(0.88), _similarity(0.92)])
        assert result.metadata["max_similarity"] == 0.92

    def test_metadata_includes_avg_similarity(self):
        result = evaluate_evidence_detailed([_similarity(0.88), _similarity(0.92)])
        assert result.metadata["avg_similarity"] == pytest.approx(0.90)

    def test_metadata_includes_decision_reason(self):
        result = evaluate_evidence_detailed([_similarity(0.95)])
        assert result.metadata["decision_reason"] == "high_similarity"

    def test_metadata_liveness_failure_reason(self):
        result = evaluate_evidence_detailed([_similarity(0.95), _liveness("FAIL")])
        assert result.metadata["decision_reason"] == "liveness_failure"

    def test_metadata_near_zone_reason(self):
        result = evaluate_evidence_detailed([_similarity(0.65)])
        assert result.metadata["decision_reason"] == "near_threshold_zone"

    def test_metadata_poor_quality_reason(self):
        result = evaluate_evidence_detailed([_similarity(0.90), _quality("POOR")])
        assert result.metadata["decision_reason"] == "high_similarity_but_poor_quality"

    def test_metadata_insufficient_reason(self):
        result = evaluate_evidence_detailed([_quality("POOR")])
        assert result.metadata["decision_reason"] == "insufficient_evidence"

    def test_metadata_providers_used(self):
        result = evaluate_evidence_detailed([
            _similarity(0.90, provider_name="uniface"),
        ])
        assert result.metadata["providers_used"] == ["uniface"]


class TestSecurityInvariants:
    """Security invariants — must never be violated."""

    def test_client_cannot_submit_threshold(self):
        """Threshold is read-only from config, not from API request."""
        from app.api.v1.identity_verification import VerifyFaceRequest
        # VerifyFaceRequest does not have a threshold field
        fields = VerifyFaceRequest.model_fields
        assert "threshold" not in fields
        assert "match_threshold" not in fields

    def test_decision_not_deterministic_without_evidence(self):
        """No evidence → INCONCLUSIVE, never a decision."""
        decision, _ = evaluate_evidence([])
        assert decision == "INCONCLUSIVE"

    def test_liveness_fail_always_no_match(self):
        """Liveness failure → NO_MATCH regardless of similarity."""
        high_sim = [_similarity(0.99), _liveness("FAIL")]
        low_sim = [_similarity(0.10), _liveness("FAIL")]
        assert evaluate_evidence(high_sim)[0] == "NO_MATCH"
        assert evaluate_evidence(low_sim)[0] == "NO_MATCH"

    def test_no_composite_score_leakage(self):
        """Decision metadata never exposes a composite score."""
        result = evaluate_evidence_detailed([_similarity(0.90), _liveness("PASS")])
        assert "composite_score" not in result.metadata
        assert "final_score" not in result.metadata

    def test_provider_never_directly_authorizes(self):
        """Provider evidence is just data; authorization is decision engine."""
        # Even with perfect provider data, decision engine is the gatekeeper
        result = evaluate_evidence_detailed([_similarity(1.0)])
        assert result.decision == "MATCH"
        # The metadata shows the engine made the decision
        assert result.metadata["decision_reason"] == "high_similarity"


class TestConfigValidation:
    """Test that Settings validates decision policy configuration."""

    def test_default_threshold_valid(self):
        settings = Settings()
        assert settings.IDENTITY_VERIFICATION_MATCH_THRESHOLD == 0.85

    def test_default_near_factor_valid(self):
        settings = Settings()
        assert settings.IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR == 0.7

    def test_threshold_zero_raises(self):
        with pytest.raises(Exception):
            Settings(IDENTITY_VERIFICATION_MATCH_THRESHOLD=0.0)

    def test_threshold_negative_raises(self):
        with pytest.raises(Exception):
            Settings(IDENTITY_VERIFICATION_MATCH_THRESHOLD=-0.1)

    def test_threshold_above_one_raises(self):
        with pytest.raises(Exception):
            Settings(IDENTITY_VERIFICATION_MATCH_THRESHOLD=1.1)

    def test_near_factor_zero_raises(self):
        with pytest.raises(Exception):
            Settings(IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR=0.0)

    def test_near_factor_negative_raises(self):
        with pytest.raises(Exception):
            Settings(IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR=-0.1)

    def test_near_factor_above_one_raises(self):
        with pytest.raises(Exception):
            Settings(IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR=1.1)

    def test_threshold_one_is_valid(self):
        settings = Settings(IDENTITY_VERIFICATION_MATCH_THRESHOLD=1.0)
        assert settings.IDENTITY_VERIFICATION_MATCH_THRESHOLD == 1.0

    def test_near_factor_one_is_valid(self):
        settings = Settings(IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR=1.0)
        assert settings.IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR == 1.0

    def test_threshold_small_positive_is_valid(self):
        settings = Settings(IDENTITY_VERIFICATION_MATCH_THRESHOLD=0.01)
        assert settings.IDENTITY_VERIFICATION_MATCH_THRESHOLD == 0.01


class TestEvidenceRecordEdgeCases:
    """Test edge cases in evidence record processing."""

    def test_confidence_used_over_signal_value(self):
        """When both confidence and signal_value are present, confidence is preferred."""
        result = evaluate_evidence_detailed([
            _evidence("similarity_score", "0.50", confidence=0.90),
        ])
        assert result.metadata["max_similarity"] == 0.90
        assert result.decision == "MATCH"

    def test_missing_confidence_falls_back_to_signal_value(self):
        """When confidence is None, signal_value is used."""
        result = evaluate_evidence_detailed([
            _evidence("similarity_score", "0.90", confidence=None),
        ])
        assert result.metadata["max_similarity"] == 0.90
        assert result.decision == "MATCH"

    def test_invalid_signal_value_ignored(self):
        """Non-numeric signal values are ignored gracefully."""
        result = evaluate_evidence_detailed([
            _evidence("similarity_score", "invalid"),
        ])
        assert result.metadata["similarity_scores_count"] == 0
        assert result.decision == "INCONCLUSIVE"

    def test_out_of_range_signal_value_ignored(self):
        """Signal values outside [0.0, 1.0] are ignored."""
        result = evaluate_evidence_detailed([
            _evidence("similarity_score", "1.5"),
            _evidence("similarity_score", "-0.1"),
        ])
        assert result.metadata["similarity_scores_count"] == 0

    def test_signal_value_at_zero(self):
        result = evaluate_evidence_detailed([
            _evidence("similarity_score", "0.0"),
        ])
        assert result.metadata["max_similarity"] == 0.0

    def test_signal_value_at_one(self):
        result = evaluate_evidence_detailed([
            _evidence("similarity_score", "1.0"),
        ])
        assert result.metadata["max_similarity"] == 1.0


class TestRegression:
    """Regression tests — ensure existing behavior is preserved."""

    def test_high_similarity_match(self):
        decision, reasoning = evaluate_evidence([_similarity(0.95)])
        assert decision == "MATCH"
        assert "0.950" in reasoning

    def test_low_similarity_no_match(self):
        decision, reasoning = evaluate_evidence([_similarity(0.45)])
        assert decision == "NO_MATCH"
        assert "0.450" in reasoning

    def test_near_threshold_inconclusive(self):
        decision, reasoning = evaluate_evidence([_similarity(0.65)])
        assert decision == "INCONCLUSIVE"
        assert "near threshold" in reasoning

    def test_liveness_failure(self):
        decision, reasoning = evaluate_evidence([_similarity(0.95), _liveness("FAIL")])
        assert decision == "NO_MATCH"
        assert "Liveness" in reasoning

    def test_quality_issue_with_high_similarity(self):
        decision, reasoning = evaluate_evidence([_similarity(0.92), _quality("POOR")])
        assert decision == "INCONCLUSIVE"
        assert "quality" in reasoning.lower()

    def test_liveness_pass_no_similarity(self):
        decision, reasoning = evaluate_evidence([_liveness("PASS")])
        assert decision == "INCONCLUSIVE"
        assert "no similarity" in reasoning.lower() or "insufficient" in reasoning.lower()

    def test_no_evidence(self):
        decision, reasoning = evaluate_evidence([])
        assert decision == "INCONCLUSIVE"
        assert "No evidence" in reasoning
