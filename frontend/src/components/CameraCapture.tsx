"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

export type CameraState =
  | "idle"
  | "requesting"
  | "active"
  | "captured"
  | "error"
  | "unsupported";

export interface CameraCaptureHandle {
  grabFrame: () => Promise<Blob | null>;
  stop: () => void;
  getState: () => CameraState;
}

interface CameraCaptureProps {
  onCapture: (blob: Blob, dataUrl: string) => void;
  onRetake: () => void;
  disabled?: boolean;
  /** Start the camera immediately on mount (no Initialize Camera button). */
  autoStart?: boolean;
  /** Keep the stream live after grabbing frames; hide manual Capture/Retake. */
  liveMode?: boolean;
  /** Fired when camera becomes ready or errors (for parent status UI). */
  onStateChange?: (state: CameraState, message?: string) => void;
}

const CameraCapture = forwardRef<CameraCaptureHandle, CameraCaptureProps>(
  function CameraCapture(
    {
      onCapture,
      onRetake,
      disabled = false,
      autoStart = false,
      liveMode = false,
      onStateChange,
    },
    ref,
  ) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const stateRef = useRef<CameraState>("idle");
    const [state, setState] = useState<CameraState>("idle");
    const [errorMessage, setErrorMessage] = useState("");
    const [capturedUrl, setCapturedUrl] = useState<string | null>(null);

    const setAppState = useCallback(
      (next: CameraState, message = "") => {
        stateRef.current = next;
        setState(next);
        if (message !== undefined) setErrorMessage(message);
        onStateChange?.(next, message);
      },
      [onStateChange],
    );

    const stopTracks = useCallback(() => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
    }, []);

    useEffect(() => {
      return () => {
        stopTracks();
        if (capturedUrl) URL.revokeObjectURL(capturedUrl);
      };
    }, [stopTracks, capturedUrl]);

    const startCamera = useCallback(async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        setAppState("unsupported", "Camera is not supported in this browser");
        return;
      }
      setAppState("requesting", "");
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: "user",
            width: { ideal: 640 },
            height: { ideal: 480 },
          },
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setAppState("active", "");
      } catch (err: unknown) {
        if (err instanceof DOMException) {
          if (err.name === "NotAllowedError") {
            setAppState(
              "error",
              "Camera permission denied. Please allow camera access.",
            );
          } else if (err.name === "NotFoundError") {
            setAppState("error", "No camera found on this device.");
          } else {
            setAppState("error", `Camera error: ${err.message}`);
          }
        } else {
          setAppState("error", "Camera unavailable");
        }
      }
    }, [setAppState]);

    useEffect(() => {
      if (autoStart && stateRef.current === "idle") {
        void startCamera();
      }
    }, [autoStart, startCamera]);

    const grabFrame = useCallback(async (): Promise<Blob | null> => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
        return null;
      }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) return null;
      ctx.drawImage(video, 0, 0);
      return new Promise((resolve) => {
        canvas.toBlob(
          (blob) => resolve(blob),
          "image/jpeg",
          0.92,
        );
      });
    }, []);

    const captureFrame = async () => {
      const blob = await grabFrame();
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      setCapturedUrl(url);
      if (!liveMode) {
        stopTracks();
        setAppState("captured", "");
      }
      onCapture(blob, url);
    };

    const retake = () => {
      if (capturedUrl) {
        URL.revokeObjectURL(capturedUrl);
        setCapturedUrl(null);
      }
      onRetake();
      startCamera();
    };

    useImperativeHandle(
      ref,
      () => ({
        grabFrame,
        stop: stopTracks,
        getState: () => stateRef.current,
      }),
      [grabFrame, stopTracks],
    );

    const showIdleControls = !autoStart && !liveMode && state === "idle";

    return (
      <div className="border border-[var(--border)] bg-[#0a0a0a] rounded">
        <div className="px-4 py-2 border-b border-[var(--border)] flex items-center justify-between">
          <span className="eg-mono-sm text-[var(--text-secondary)]">
            Camera
          </span>
          {state === "active" && (
            <span className="eg-mono-sm text-[var(--text-tertiary)]">Live</span>
          )}
          {state === "captured" && (
            <span className="eg-mono-sm text-[var(--text-tertiary)]">
              Captured
            </span>
          )}
        </div>

        <div className="relative aspect-[4/3] bg-black">
          <canvas ref={canvasRef} className="hidden" />

          {showIdleControls && (
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
                Starting camera...
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

          {state === "active" && liveMode && (
            <div className="absolute inset-0 pointer-events-none border-2 border-[var(--accent)]/40 m-6 rounded-full" />
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
              <span className="eg-mono text-[var(--danger)] text-center">
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

        {state === "active" && !liveMode && (
          <div className="px-4 py-3 border-t border-[var(--border)] flex justify-center">
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
          <div className="px-4 py-3 border-t border-[var(--border)] flex justify-center">
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
  },
);

export default CameraCapture;
