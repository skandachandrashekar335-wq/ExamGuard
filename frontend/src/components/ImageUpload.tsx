"use client";

import { useRef, useState } from "react";

interface ImageUploadProps {
  label: string;
  onImage: (blob: Blob, dataUrl: string) => void;
  onClear: () => void;
  disabled?: boolean;
}

export default function ImageUpload({
  label,
  onImage,
  onClear,
  disabled = false,
}: ImageUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      setPreview(dataUrl);
      onImage(file, dataUrl);
    };
    reader.readAsDataURL(file);
  };

  const clear = () => {
    setPreview(null);
    setFileName(null);
    if (inputRef.current) inputRef.current.value = "";
    onClear();
  };

  return (
    <div className="border border-white/10 bg-[#0a0a0a]">
      <div className="px-4 py-2 border-b border-white/10 flex items-center justify-between">
        <span className="eg-mono-sm text-[var(--text-secondary)]">{label}</span>
        {fileName && (
          <span className="eg-mono-sm text-[var(--text-tertiary)] truncate max-w-[120px]">
            {fileName}
          </span>
        )}
      </div>

      <div className="relative aspect-[4/3] bg-black">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={preview}
            alt="Reference"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6">
            <span className="eg-mono text-[var(--text-tertiary)] text-center text-[10px]">
              Upload enrollment photo
            </span>
            <button
              onClick={() => inputRef.current?.click()}
              disabled={disabled}
              className="eg-btn px-4 py-2 disabled:opacity-30"
            >
              Select Image
            </button>
          </div>
        )}
      </div>

      {preview && (
        <div className="px-4 py-3 border-t border-white/10 flex justify-center">
          <button
            onClick={clear}
            disabled={disabled}
            className="eg-btn px-4 py-2 disabled:opacity-30"
          >
            Remove
          </button>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png"
        onChange={handleChange}
        className="hidden"
        aria-label={label}
      />
    </div>
  );
}
