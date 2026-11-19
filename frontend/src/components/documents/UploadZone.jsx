/**
 * UploadZone - drag & drop file picker for PDF/TXT.
 *
 * Validates the file in the browser (type + size) before it ever reaches
 * the backend, which validates it again including the real file signature.
 */
import { useRef, useState } from 'react';
import { FileText, Upload, X } from 'lucide-react';
import { ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB } from '../../utils/constants';
import { formatBytes } from '../../utils/formatters';

export default function UploadZone({ file, onFileSelect, onClear, error, disabled = false }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  function handleFiles(fileList) {
    const picked = fileList?.[0];
    if (picked) onFileSelect(picked);
  }

  function handleDrop(event) {
    event.preventDefault();
    setIsDragging(false);
    if (!disabled) handleFiles(event.dataTransfer.files);
  }

  if (file) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-indigo-200 bg-indigo-50/60 px-4 py-3.5">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-indigo-600 shadow-sm">
          <FileText className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-900">{file.name}</p>
          <p className="text-xs text-slate-500">
            {formatBytes(file.size)} · {file.name.split('.').pop().toUpperCase()}
          </p>
        </div>
        <button
          type="button"
          onClick={onClear}
          disabled={disabled}
          className="rounded-lg p-1.5 text-slate-400 transition hover:bg-white hover:text-rose-600"
          aria-label="Remove selected file"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-5 py-9 text-center transition ${
          isDragging
            ? 'border-indigo-400 bg-indigo-50'
            : 'border-slate-300 bg-slate-50 hover:border-indigo-300 hover:bg-indigo-50/40'
        } ${disabled ? 'pointer-events-none opacity-60' : ''}`}
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-indigo-600 shadow-sm">
          <Upload className="h-5 w-5" />
        </span>
        <div>
          <p className="text-sm font-semibold text-slate-800">
            Drag &amp; drop your document here
          </p>
          <p className="mt-1 text-xs text-slate-500">
            or <span className="font-semibold text-indigo-600">browse files</span>
          </p>
        </div>
        <p className="text-[11px] text-slate-400">
          {ALLOWED_EXTENSIONS.join(' and ').toUpperCase()} · max {MAX_FILE_SIZE_MB} MB
        </p>

        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept={ALLOWED_EXTENSIONS.join(',')}
          onChange={(event) => {
            handleFiles(event.target.files);
            event.target.value = ''; // allow picking the same file again
          }}
        />
      </div>

      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
    </div>
  );
}
