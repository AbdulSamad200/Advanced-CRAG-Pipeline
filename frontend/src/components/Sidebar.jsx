// src/components/Sidebar.jsx
import { useState, useRef, useCallback } from 'react'
import {
  MessageSquarePlus, Trash2, FileText, UploadCloud,
  CheckCircle2, AlertCircle, Loader2, ChevronDown, ChevronUp,
  Cpu, Wifi, WifiOff,
} from 'lucide-react'
import { uploadPDF, listPDFs } from '../api/ragApi.js'

function HealthBadge({ health }) {
  if (!health) return null
  const ok = health.rag_ready
  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-mono ${
      ok ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
         : 'bg-red-500/10 text-red-400 border border-red-500/20'
    }`}>
      {ok ? <Wifi size={10} /> : <WifiOff size={10} />}
      {ok ? 'RAG online' : 'RAG offline'}
    </div>
  )
}

function ConvItem({ conv, active, onSelect, onDelete }) {
  const [hover, setHover] = useState(false)
  return (
    <button
      onClick={() => onSelect(conv.id)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={`w-full text-left flex items-center gap-2.5 px-3 py-2.5 rounded-lg transition-all duration-150 group
        ${active
          ? 'bg-accent/15 border border-accent/25 text-white'
          : 'hover:bg-panel text-slate-400 hover:text-slate-200 border border-transparent'
        }`}
    >
      <MessageSquarePlus size={13} className={active ? 'text-accent' : 'text-muted'} />
      <span className="flex-1 text-xs font-body truncate">{conv.title}</span>
      {hover && !active && (
        <span
          onClick={e => { e.stopPropagation(); onDelete(conv.id) }}
          className="text-slate-600 hover:text-red-400 transition-colors p-0.5 rounded"
        >
          <Trash2 size={11} />
        </span>
      )}
    </button>
  )
}

function PDFSection() {
  const [pdfs, setPdfs]           = useState([])
  const [expanded, setExpanded]   = useState(true)
  const [dragging, setDragging]   = useState(false)
  const [uploads, setUploads]     = useState([]) // { name, progress, status, error }
  const inputRef = useRef()

  const fetchPDFs = useCallback(async () => {
    try {
      const data = await listPDFs()
      setPdfs(data.pdfs || [])
    } catch { /* ignore */ }
  }, [])

  const handleFiles = async (files) => {
    const pdfFiles = Array.from(files).filter(f => f.name.endsWith('.pdf'))
    if (!pdfFiles.length) return

    for (const file of pdfFiles) {
      const entry = { name: file.name, progress: 0, status: 'uploading', error: null }
      setUploads(prev => [...prev.filter(u => u.name !== file.name), entry])

      try {
        await uploadPDF(file, (pct) => {
          setUploads(prev => prev.map(u => u.name === file.name ? { ...u, progress: pct } : u))
        })
        setUploads(prev => prev.map(u => u.name === file.name ? { ...u, status: 'done', progress: 100 } : u))
        await fetchPDFs()
      } catch (err) {
        setUploads(prev => prev.map(u => u.name === file.name
          ? { ...u, status: 'error', error: err.message } : u))
      }
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="mt-auto border-t border-border pt-3">
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-2 px-1 py-1 text-slate-500 hover:text-slate-300 transition-colors text-xs font-display font-semibold tracking-wide uppercase mb-2"
      >
        <FileText size={11} />
        <span>PDF Knowledge Base</span>
        <span className="ml-auto">{expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}</span>
      </button>

      {expanded && (
        <div className="space-y-2 animate-fade-in">
          {/* Drop zone */}
          <div
            onDragEnter={e => { e.preventDefault(); setDragging(true) }}
            onDragOver={e => e.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={`rounded-lg border-2 border-dashed p-4 text-center cursor-pointer transition-all duration-200
              ${dragging
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-border hover:border-muted hover:bg-panel/50 text-slate-600 hover:text-slate-400'
              }`}
          >
            <UploadCloud size={18} className="mx-auto mb-1.5" />
            <p className="text-xs font-body">Drop PDFs or click to browse</p>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={e => handleFiles(e.target.files)}
            />
          </div>

          {/* Upload status */}
          {uploads.map(u => (
            <div key={u.name} className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-panel/60 border border-border">
              {u.status === 'uploading' && <Loader2 size={11} className="animate-spin text-accent flex-shrink-0" />}
              {u.status === 'done'      && <CheckCircle2 size={11} className="text-emerald-400 flex-shrink-0" />}
              {u.status === 'error'     && <AlertCircle size={11} className="text-red-400 flex-shrink-0" />}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-mono text-slate-300 truncate">{u.name}</p>
                {u.status === 'uploading' && (
                  <div className="mt-0.5 h-0.5 bg-border rounded-full overflow-hidden">
                    <div className="h-full bg-accent transition-all" style={{ width: `${u.progress}%` }} />
                  </div>
                )}
                {u.status === 'error' && <p className="text-xs text-red-400 truncate">{u.error}</p>}
              </div>
            </div>
          ))}

          {/* Existing PDFs */}
          {pdfs.length > 0 && (
            <div className="space-y-1">
              {pdfs.map(p => (
                <div key={p.name} className="flex items-center gap-2 px-2 py-1 rounded text-slate-500">
                  <FileText size={10} className="text-accent/60 flex-shrink-0" />
                  <span className="text-xs font-mono truncate">{p.name}</span>
                  <span className="ml-auto text-xs text-slate-700">{p.size_kb}kb</span>
                </div>
              ))}
            </div>
          )}

          {pdfs.length === 0 && uploads.length === 0 && (
            <p className="text-xs text-slate-700 font-mono text-center py-1">No PDFs ingested yet</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function Sidebar({ conversations, activeId, onSelect, onNew, onDelete, health }) {
  return (
    <aside className="w-60 flex-shrink-0 flex flex-col h-full bg-deep/90 border-r border-border relative z-10">
      {/* Header */}
      <div className="px-4 pt-5 pb-4 border-b border-border/50">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-7 h-7 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center">
            <Cpu size={13} className="text-accent" />
          </div>
          <div>
            <h1 className="text-sm font-display font-bold text-white tracking-tight">RAG · Research</h1>
            <p className="text-xs text-slate-600 font-mono">CRAG Pipeline v2</p>
          </div>
        </div>
        <HealthBadge health={health} />
      </div>

      {/* New chat button */}
      <div className="px-3 pt-3 pb-2">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-accent/10 hover:bg-accent/20 border border-accent/20 hover:border-accent/40 text-accent transition-all duration-150 text-xs font-display font-semibold"
        >
          <MessageSquarePlus size={13} />
          New conversation
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5 min-h-0">
        {conversations.length > 0 && (
          <p className="text-xs font-display font-semibold text-slate-700 uppercase tracking-wide px-1 mb-2">History</p>
        )}
        {conversations.map(conv => (
          <ConvItem
            key={conv.id}
            conv={conv}
            active={conv.id === activeId}
            onSelect={onSelect}
            onDelete={onDelete}
          />
        ))}
      </div>

      {/* PDF upload section */}
      <div className="px-3 pb-4">
        <PDFSection />
      </div>
    </aside>
  )
}
