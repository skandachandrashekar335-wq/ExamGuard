"""Verify real UniFace inference with genuine ONNX neural models and server-side decision logic."""

import io
import cv2
import numpy as np
from skimage import data

from app.services.face_verification.providers.uniface_provider import UniFaceProvider
from app.services.face_verification.types import FaceVerificationRequest
from app.services.face_verification.providers.deterministic import ProviderUnavailableError
from app.services.identity_verification_decision import evaluate_evidence_detailed
from app.models.identity_verification import IdentityVerificationEvidence

def image_to_jpeg_bytes(img_bgr: np.ndarray) -> bytes:
    _, buf = cv2.imencode(".jpg", img_bgr)
    return buf.tobytes()

def run_uniface_verification():
    print("=== UniFace Neural Inference & Decision Verification ===")
    
    # 1. Inspect ONNX model cache
    import os
    model_dir = os.path.expanduser("~/.uniface/models")
    print(f"Model Directory: {model_dir}")
    models = sorted(os.listdir(model_dir))
    for m in models:
        mpath = os.path.join(model_dir, m)
        size_mb = os.path.getsize(mpath) / (1024 * 1024)
        print(f"  - Loaded ONNX Weight File: {m} ({size_mb:.2f} MB)")
        
    # 2. Instantiate real UniFace Provider
    provider = UniFaceProvider(anti_spoofing=True)
    status = provider.health_check()
    print(f"\nProvider Health: {status.available} ({status.message})")
    assert status.available, "Provider must be available"
    
    # Prepare test images:
    # Face A: Astronaut (BGR)
    face_a_bgr = cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)
    face_a_bytes = image_to_jpeg_bytes(face_a_bgr)
    
    # Face A probe (slightly shifted/scaled probe of same person)
    h, w = face_a_bgr.shape[:2]
    # Crop slightly and resize back to original size
    cropped = face_a_bgr[10:h-10, 10:w-10]
    face_a_probe_bgr = cv2.resize(cropped, (w, h))
    face_a_probe_bytes = image_to_jpeg_bytes(face_a_probe_bgr)
    
    # Face B: Photographer (Camera image, grayscale to BGR)
    face_b_bgr = cv2.cvtColor(data.camera(), cv2.COLOR_GRAY2BGR)
    face_b_bytes = image_to_jpeg_bytes(face_b_bgr)
    
    # Non-face: Blank image
    blank_bgr = np.zeros((300, 300, 3), dtype=np.uint8)
    blank_bytes = image_to_jpeg_bytes(blank_bgr)

    print("\n--- Test 1: Genuine Matching Candidate (Face A vs Face A Probe) ---")
    req_match = FaceVerificationRequest(
        reference_image=face_a_bytes,
        probe_image=face_a_probe_bytes,
    )
    result_match = provider.verify(req_match)
    print(f"  Similarity Score:  {result_match.identity_match_score:.4f}")
    print(f"  Liveness Score:    {result_match.liveness_score:.4f}")
    print(f"  Liveness Passed:   {result_match.liveness_passed}")
    print(f"  Provider Metadata: {result_match.evidence_metadata}")
    
    # Feed into ExamGuard Server-Side Decision Engine
    evidence_match = [
        IdentityVerificationEvidence(
            signal_type="similarity_score",
            signal_value=f"{result_match.identity_match_score:.4f}",
            provider_name="uniface",
        ),
        IdentityVerificationEvidence(
            signal_type="liveness",
            signal_value="PASS" if result_match.liveness_passed else "FAIL",
            provider_name="uniface",
        ),
    ]
    decision_res = evaluate_evidence_detailed(evidence_match)
    print(f"  Decision Engine Verdict: {decision_res.decision}")
    print(f"  Reasoning: {decision_res.reasoning}")
    assert decision_res.decision == "MATCH", f"Expected MATCH, got {decision_res.decision}"
    assert result_match.identity_match_score >= 0.68, "Match score must be >= 0.68"

    print("\n--- Test 2: Different Candidate Impersonation (Face A vs Face B) ---")
    req_no_match = FaceVerificationRequest(
        reference_image=face_a_bytes,
        probe_image=face_b_bytes,
    )
    result_no_match = provider.verify(req_no_match)
    print(f"  Similarity Score:  {result_no_match.identity_match_score:.4f}")
    print(f"  Liveness Passed:   {result_no_match.liveness_passed}")
    
    evidence_no_match = [
        IdentityVerificationEvidence(
            signal_type="similarity_score",
            signal_value=f"{result_no_match.identity_match_score:.4f}",
            provider_name="uniface",
        ),
        IdentityVerificationEvidence(
            signal_type="liveness",
            signal_value="PASS" if result_no_match.liveness_passed else "FAIL",
            provider_name="uniface",
        ),
    ]
    decision_no_match = evaluate_evidence_detailed(evidence_no_match)
    print(f"  Decision Engine Verdict: {decision_no_match.decision}")
    print(f"  Reasoning: {decision_no_match.reasoning}")
    assert decision_no_match.decision == "NO_MATCH", f"Expected NO_MATCH, got {decision_no_match.decision}"
    assert result_no_match.identity_match_score < 0.52, "Impersonator score must be < 0.52"

    print("\n--- Test 3: Inconclusive Decision Boundary (0.52 <= score < 0.68) ---")
    # Test boundary enforcement with genuine decision engine rules
    inconclusive_score = 0.615  # Exactly in the inconclusive band
    evidence_inconclusive = [
        IdentityVerificationEvidence(
            signal_type="similarity_score",
            signal_value=str(inconclusive_score),
            provider_name="uniface",
        ),
        IdentityVerificationEvidence(
            signal_type="liveness",
            signal_value="PASS",
            provider_name="uniface",
        ),
    ]
    decision_inc = evaluate_evidence_detailed(evidence_inconclusive)
    print(f"  Similarity Score Tested: {inconclusive_score}")
    print(f"  Decision Engine Verdict: {decision_inc.decision}")
    print(f"  Reasoning: {decision_inc.reasoning}")
    assert decision_inc.decision == "INCONCLUSIVE", f"Expected INCONCLUSIVE, got {decision_inc.decision}"

    print("\n--- Test 4: Anti-Spoofing Detection Failure Path ---")
    # A presentation attack with failing liveness must immediately trigger NO_MATCH
    evidence_spoof = [
        IdentityVerificationEvidence(
            signal_type="similarity_score",
            signal_value="0.940",  # High similarity
            provider_name="uniface",
        ),
        IdentityVerificationEvidence(
            signal_type="liveness",
            signal_value="FAIL",  # Spoof detected
            provider_name="uniface",
        ),
    ]
    decision_spoof = evaluate_evidence_detailed(evidence_spoof)
    print(f"  Decision Engine Verdict on Spoof: {decision_spoof.decision}")
    print(f"  Reasoning: {decision_spoof.reasoning}")
    assert decision_spoof.decision == "NO_MATCH", f"Expected NO_MATCH on spoof, got {decision_spoof.decision}"

    print("\n--- Test 5: Missing Face Rejection Path ---")
    req_no_face = FaceVerificationRequest(
        reference_image=face_a_bytes,
        probe_image=blank_bytes,
    )
    try:
        provider.verify(req_no_face)
        raise AssertionError("Should have raised ProviderUnavailableError on blank image")
    except ProviderUnavailableError as e:
        print(f"  Correctly raised ProviderUnavailableError: {e.error.error_type} - {e.error.message}")
        assert e.error.error_type.name == "NO_FACE_DETECTED"

    print("\nALL REAL UNIFACE INFERENCE & DECISION VERIFICATION TESTS PASSED.")

if __name__ == "__main__":
    run_uniface_verification()
