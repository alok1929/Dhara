'use client'

import { useRef, useState } from 'react'
import { Plus, X } from 'lucide-react'
import Button from '../../ui/Button'
import ErrorBanner from '../../ui/ErrorBanner'
import LlmKeyRequiredBanner from '../../LlmKeyRequiredBanner'
import { MetadataFileList } from '../ConsoleUploadChoice'
import { isDatasetFile } from '../../../lib/datasetUpload'
import { formatFileSize } from '../../../lib/chatConsoleHelpers'

function FileRow({ file, onRemove }) {
  return (
    <li className="flex items-center justify-between gap-2 rounded-md border border-line/70 bg-cream/95 px-2.5 py-1.5 text-[12.5px] text-ink">
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium">{file.name}</div>
        <div className="text-[11px] text-ink-soft">{formatFileSize(file.size)}</div>
      </div>
      <button
        type="button"
        className="flex h-6 w-6 flex-none items-center justify-center rounded text-ink-soft hover:bg-white hover:text-[#b91c1c]"
        onClick={onRemove}
        aria-label="Remove file"
      >
        <X className="h-3.5 w-3.5" strokeWidth={2} />
      </button>
    </li>
  )
}

export default function ChatUploadScreen({
  hasLlmKey,
  onGoSettings,
  datasetFiles,
  metadataFiles,
  onDatasetAdd,
  onDatasetRemove,
  onMetadataAdd,
  onMetadataRemove,
  onStartProcessing,
  processing,
  error,
  onClearError,
}) {
  const datasetRef = useRef(null)
  const metadataRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const blocked = !hasLlmKey || processing
  const hasFiles = datasetFiles.length > 0

  const takeDatasets = (list) => {
    const files = Array.from(list || []).filter((f) => isDatasetFile(f.name))
    if (files.length) onDatasetAdd?.(files)
  }

  const takeMetadata = (list) => {
    const files = Array.from(list || []).filter((f) => /\.(xlsx|xls)$/i.test(f.name))
    if (files.length) onMetadataAdd?.(files)
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 py-4">
      <div className="text-center">
        <h1 className="font-display text-[26px] font-medium text-ink">Let&apos;s prepare your data</h1>
        <p className="mt-2 text-[15px] leading-relaxed text-ink-soft">
          Upload your documents and metadata files to get started. Dhara will guide you through the rest.
        </p>
      </div>

      {!hasLlmKey && <LlmKeyRequiredBanner onGoSettings={onGoSettings} />}

      <input
        ref={datasetRef}
        type="file"
        accept=".pdf,.xlsx,.xls,.csv"
        multiple
        className="hidden"
        disabled={blocked}
        onChange={(e) => {
          takeDatasets(e.target.files)
          e.target.value = ''
        }}
      />
      <input
        ref={metadataRef}
        type="file"
        accept=".xlsx,.xls"
        multiple
        className="hidden"
        disabled={blocked}
        onChange={(e) => {
          takeMetadata(e.target.files)
          e.target.value = ''
        }}
      />

      <div
        role="button"
        tabIndex={blocked ? -1 : 0}
        onClick={() => !blocked && datasetRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            if (!blocked) datasetRef.current?.click()
          }
        }}
        onDragOver={(e) => { if (!blocked) { e.preventDefault(); setDragging(true) } }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!blocked) takeDatasets(e.dataTransfer.files)
        }}
        className={`flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed px-6 py-10 text-center transition-colors ${
          blocked
            ? 'cursor-not-allowed border-line bg-mist/50 opacity-70'
            : dragging
              ? 'cursor-pointer border-teal/40 bg-sage'
              : 'cursor-pointer border-line bg-white hover:border-teal/35 hover:bg-sage/60'
        }`}
      >
        <Plus className="h-6 w-6 text-teal" strokeWidth={2} aria-hidden />
        <div className="text-[16px] font-semibold text-ink">Drop files here</div>
        <div className="max-w-sm text-[13px] text-ink-soft">
          PDF, XLSX, CSV, and optional metadata workbooks. SQL database connections stay in Guided view.
        </div>
        <Button
          variant="secondary"
          size="sm"
          type="button"
          disabled={blocked}
          onClick={(e) => {
            e.stopPropagation()
            datasetRef.current?.click()
          }}
        >
          Browse files
        </Button>
      </div>

      {hasFiles && (
        <ul className="flex list-none flex-col gap-1.5">
          {datasetFiles.map((f, i) => (
            <FileRow key={`${f.name}-${i}`} file={f} onRemove={() => onDatasetRemove?.(i)} />
          ))}
        </ul>
      )}

      <div className="rounded-xl border border-line/90 bg-white p-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] font-semibold text-ink-soft">Metadata (optional)</span>
          <Button
            variant="secondary"
            size="sm"
            type="button"
            disabled={blocked}
            onClick={() => metadataRef.current?.click()}
          >
            Add metadata
          </Button>
        </div>
        <MetadataFileList files={metadataFiles} onRemove={onMetadataRemove} />
      </div>

      {error && (
        <div className="flex flex-col gap-2">
          <ErrorBanner>{error}</ErrorBanner>
          <Button variant="secondary" size="sm" className="self-start" onClick={onClearError}>Try again</Button>
        </div>
      )}

      <div className="flex justify-center pt-2">
        <Button
          disabled={blocked || !hasFiles}
          loading={processing}
          onClick={() => !blocked && hasFiles && onStartProcessing?.()}
        >
          Start Processing
        </Button>
      </div>
    </div>
  )
}
