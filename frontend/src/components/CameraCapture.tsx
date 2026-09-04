"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export type CameraState =
  | "idle"
  | "requesting"
  | "active"
  | "captured"
  | "error"
  | "unsupported";

interface CameraCaptureProps {
  onCapture: (blob: Blob, dataUrl: string) => void;
  onRetake: () => void;
  disabled?: boolean;
}

export default function CameraCapture({
  onCapture,
  onRetake,
  disabled = false,
}: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [state, setState] = useState<CameraState>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [capturedUrl, setCapturedUrl] = useState<string | null>(null);

  const stopTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      stopTracks();
      if (capturedUrl) URL.revokeObjectURL(capturedUrl);
    };
  }, [stopTracks, capturedUrl]);

  const startCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setState("unsupported");
      setErrorMessage("Camera is not supported in this browser");
      return;
    }
    setState("requesting");
    setErrorMessage("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setState("active");
    } catch (err: unknown) {
      setState("error");
      if (err instanceof DOMException) {
        if (err.name === "NotAllowedError") {
          setErrorMessage("Camera permission denied. Please allow camera access.");
        } else if (err.name === "NotFoundError") {
          setErrorMessage("No camera found on this device.");
        } else {
          setErrorMessage(`Camera error: ${err.message}`);
        }
      } else {
        setErrorMessage("Camera unavailable");
      }
    }
  };

  const captureFrame = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (blob) {
          const url = URL.createObjectURL(blob);
          setCapturedUrl(url);
          stopTracks();
          setState("captured");
          onCapture(blob, url);
        }
      },
      "image/jpeg",
      0.92,
    );
  };

  const retake = () => {
    if (capturedUrl) {
      URL.revokeObjectURL(capturedUrl);
      setCapturedUrl(null);
    }
    onRetake();
    startCamera();
  };

  return (
    <div className="border border-white/10 bg-[#0a0a0a]">
      <div className="px-4 py-2 border-b border-white/10 flex items-center justify-between">
        <span className="eg-mono-sm text-[var(--text-secondary)]">
          Camera
        </span>
        {state === "active" && (
          <span className="eg-mono-sm text-[var(--text-tertiary)]">
            Live
          </span>
        )}
        {state === "captured" && (
          <span className="eg-mono-sm text-[var(--text-tertiary)]">
            Captured
          </span>
        )}
      </div>

      <div className="relative aspect-[4/3] bg-black">
        <canvas ref={canvasRef} className="hidden" />

        {state === "idle" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
            <button
              onClick={startCamera}
              disabled={disabled}
              className="eg-btn px-6 py-3 disabled:opacity-30"
            >
              Initialize Camera
            </button>
          </div>
        )}

        {state === "requesting" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="eg-mono text-[var(--text-tertiary)]">
              Requesting camera access...
            </span>
          </div>
        )}

        {(state === "active" || state === "requesting") && (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover"
          />
        )}

        {state === "captured" && capturedUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={capturedUrl}
            alt="Captured frame"
            className="w-full h-full object-cover"
          />
        )}

        {state === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6">
            <span className="eg-mono text-red-400 text-center">
              {errorMessage}
            </span>
            <button onClick={startCamera} className="eg-btn px-4 py-2">
              Retry
            </button>
          </div>
        )}

        {state === "unsupported" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="eg-mono text-[var(--text-tertiary)] text-center px-6">
              Camera is not available in this browser
            </span>
          </div>
        )}
      </div>

      {state === "active" && (
        <div className="px-4 py-3 border-t border-white/10 flex justify-center">
          <button
            onClick={captureFrame}
            disabled={disabled}
            className="eg-btn-primary eg-btn px-8 py-2 disabled:opacity-30"
          >
            Capture
          </button>
        </div>
      )}

      {state === "captured" && (
        <div className="px-4 py-3 border-t border-white/10 flex justify-center">
          <button
            onClick={retake}
            disabled={disabled}
            className="eg-btn px-6 py-2 disabled:opacity-30"
          >
            Retake
          </button>
        </div>
      )}
    </div>
  );
}
