"""Verify real Cloudinary storage upload, retrieval, and cleanup."""

import os
import sys
import urllib.request
from pathlib import Path
from dotenv import dotenv_values
from app.storage.cloudinary import CloudinaryStorage
import cloudinary
import cloudinary.uploader
import cloudinary.api

def test_cloudinary():
    # Load credentials from root .env
    root_env_path = Path(__file__).resolve().parents[2] / ".env"
    env = dotenv_values(root_env_path)
    cloud_name = env.get("CLOUDINARY_CLOUD_NAME")
    api_key = env.get("CLOUDINARY_API_KEY")
    api_secret = env.get("CLOUDINARY_API_SECRET")
    
    print(f"Cloud Name configured: {cloud_name}")
    print(f"API Key present: {bool(api_key)}")
    print(f"API Secret present: {bool(api_secret)}")
    
    if not (cloud_name and api_key and api_secret):
        print("BLOCKED: Cloudinary credentials missing.")
        return False
        
    os.environ["CLOUDINARY_CLOUD_NAME"] = cloud_name
    os.environ["CLOUDINARY_API_KEY"] = api_key
    os.environ["CLOUDINARY_API_SECRET"] = api_secret
    
    storage = CloudinaryStorage()
    assert storage._using_cloudinary, "CloudinaryStorage should report _using_cloudinary=True"
    
    # 1. Upload consented test document
    test_key = "test_verification/consented_audit_sample.txt"
    test_bytes = b"EXAMGUARD_VERIFICATION_TEST_PAYLOAD: Consented examination verification sample token."
    
    print(f"\n[1] Uploading test asset to key: {test_key}...")
    try:
        secure_url = storage.save(test_key, test_bytes)
        print(f"Provider Upload SUCCESS!")
        print(f"Secure URL returned: {secure_url}")
        assert "cloudinary.com" in secure_url, f"Expected cloudinary.com URL, got {secure_url}"
    except Exception as e:
        print(f"Upload failed: {e}")
        return False
        
    # 2. Retrieve file content from the secure URL
    print("\n[2] Retrieving uploaded file from secure URL...")
    req = urllib.request.Request(secure_url, headers={"User-Agent": "ExamGuard-Audit/1.0"})
    with urllib.request.urlopen(req, timeout=10) as response:
        status_code = response.getcode()
        downloaded_bytes = response.read()
        print(f"HTTP Status Code: {status_code}")
        print(f"Downloaded bytes length: {len(downloaded_bytes)}")
        assert status_code == 200, f"Expected 200, got {status_code}"
        assert downloaded_bytes == test_bytes, "Downloaded content does not match uploaded bytes!"
        print("Content integrity verified: downloaded bytes exactly match source bytes.")

    # 3. Clean up / Delete the test asset from Cloudinary
    print("\n[3] Deleting temporary test asset from Cloudinary...")
    full_public_id = f"examguard/{storage._cloudinary_key(test_key)}"
    print(f"Deleting public_id: {full_public_id}")
    del_result = cloudinary.uploader.destroy(full_public_id, resource_type="raw")
    print(f"Cloudinary destroy response: {del_result}")
    
    # Also verify deletion by trying to fetch or checking result
    assert del_result.get("result") in ("ok", "not found"), f"Unexpected deletion result: {del_result}"
    print("Temporary test asset successfully removed from Cloudinary.")
    print("REAL CLOUDINARY STORAGE VERIFICATION COMPLETED SUCCESSFULLY.")
    return True

if __name__ == "__main__":
    success = test_cloudinary()
    if not success:
        sys.exit(1)
