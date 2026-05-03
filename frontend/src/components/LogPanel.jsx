// src/components/LogPanel.jsx
import { useEffect, useRef, useState } from 'react'
import { X, Terminal, Trash2, ChevronDown } from 'lucide-react'

// ── Log line colorizer ─────────────────────────────────────
function classifyLog(text) {
  if (text.startsWith('❌') || text.toLowerCase().includes('error') || text.toLowerCase().includes('failed')) {
    return 'error'
  }
  if (text.startsWith('⚠️') || text.toLowerCase().includes('warning')) {
    return 'warn'
  }
  if (text.startsWith('✅')) return 'success'
  if (text.startsWith('🌐')) return 'web'
  if (text.startsWith('🧠')) return 'eval'
  if (text.startsWith('⚡')) return 'gen'
  if (text.startsWith('🔢') || text.startsWith('🗄️')) return 'embed'
  if (text.startsWith('📂') || text.startsWith('📄') || text.startsWith('💾')) return 'ingest'
  if (text.startsWith('─')) return 'divider'
  if (text.startsWith('    ▶') || text.startsWith('    [')) return 'detail'
  return 'info'
}

const LOG_STYLES = {
  error:   'text-red-400',
  warn:    'text-amber-400',
  success: 'text-emerald-400',
  web:     'text-cyan-400',
  eval:    'text-violet-400',
  gen:     'text-yellow-300',
  embed:   'text-blue-400',
  ingest:  'text-orange-400',
  divider: 'text-slate-700',
  detail:  'text-slate-500',
  info:    'text-slate-400',
}

function LogLine({ log }) {
  const kind = log.isError ? 'error' : classifyLog(log.text)
  const style = LOG_STYLES[kind]
  const isDivider = kind === 'divider'

  if (isDivider) {
    return (
      <div className="py-1">
        <div className="h-px bg-border/60" />
      </div>
    )
  }

  return (
    <div className={`log-line flex gap-2 py-0.5 ${style} animate-fade-in`}>
      <span className="text-slate-700 flex-shrink-0 select-none font-mono text-[10px] pt-px">
        {new Date(log.ts).toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
      </span>
      <span className="break-all">{log.text}</span>
    </div>
  )
}

// Stage badges shown as a progress indicator
const STAGES = [
  { key: 'ingest',  label: '📂 Ingest',  match: /Stage 3/ },
  { key: 'embed',   label: '🔢 Embed',   match: /Stage 4|Stage 3a/ },
  { key: 'vector',  label: '🗄️ Retrieve', match: /Stage 5/ },
  { key: 'crag',    label: '🧠 CRAG',    match: /Stage 6/ },
  { key: 'context', label: '📚 Context', match: /Stage 7/ },
  { key: 'gen',     label: '⚡ Generate', match: /Stage 8/ },
]

function PipelineProgress({ logs }) {
  const texts = logs.map(l => l.text).join('\n')
  const activeIdx = STAGES.reduce((acc, s, i) => s.match.test(texts) ? i : acc, -1)

  return (
    <div className="flex flex-wrap gap-1 px-3 py-2 border-b border-border/50">
      {STAGES.map((s, i) => (
        <span
          key={s.key}
          className={`text-[10px] font-mono px-2 py-0.5 rounded-full transition-all duration-300
            ${i < activeIdx
              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
              : i === activeIdx
              ? 'bg-accent/20 text-accent border border-accent/30 animate-pulse-slow'
              : 'bg-void text-slate-700 border border-border/50'
            }`}
        >
          {s.label}
        </span>
      ))}
    </div>
  )
}

export default function LogPanel({ logs, isLoading, onClose }) {
  const bottomRef  = useRef()
  const containerRef = useRef()
  const [autoScroll, setAutoScroll] = useState(true)
  const [cleared, setCleared] = useState([])

  // Auto-scroll when new logs arrive
  useEffect(() => {
    if (autoScroll) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  // Detect manual scroll up → disable auto-scroll
  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    setAutoScroll(atBottom)
  }

  const visibleLogs = logs.filter(l => !cleared.includes(l.id))

  return (
    <aside className="w-80 flex-shrink-0 flex flex-col h-full bg-deep/95 border-l border-border relative z-10">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-3 py-3 border-b border-border/50">
        <div className="flex items-center gap-2">
          <Terminal size={13} className="text-accent" />
          <span className="text-xs font-display font-bold text-white tracking-wide">Pipeline Logs</span>
          {isLoading && (
            <span className="flex items-center gap-1 text-xs text-accent font-mono animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-ping" />
              live
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {visibleLogs.length > 0 && (
            <button
              onClick={() => setCleared(prev => [...prev, ...logs.map(l => l.id)])}
              className="p-1.5 rounded-md text-slate-600 hover:text-slate-400 hover:bg-panel transition-colors"
              title="Clear logs"
            >
              <Trash2 size={11} />
            </button>
          )}
          {!autoScroll && (
            <button
              onClick={() => { setAutoScroll(true); bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }}
              className="p-1.5 rounded-md text-accent hover:bg-accent/10 transition-colors"
              title="Scroll to bottom"
            >
              <ChevronDown size={11} />
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-600 hover:text-slate-400 hover:bg-panel transition-colors"
          >
            <X size={11} />
          </button>
        </div>
      </div>

      {/* Pipeline progress */}
      {logs.length > 0 && <PipelineProgress logs={logs} />}

      {/* Log stream */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-3 py-2 min-h-0"
      >
        {visibleLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Terminal size={24} className="text-slate-800 mb-2" />
            <p className="text-xs text-slate-700 font-mono">
              {isLoading ? 'Waiting for pipeline...' : 'Send a query to see the pipeline in action'}
            </p>
          </div>
        ) : (
          <>
            {visibleLogs.map(log => (
              <LogLine key={log.id} log={log} />
            ))}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Footer count */}
      <div className="flex-shrink-0 px-3 py-2 border-t border-border/50">
        <p className="text-xs text-slate-700 font-mono">
          {visibleLogs.length} log lines
          {isLoading && <span className="text-accent ml-2 animate-pulse">· processing</span>}
        </p>
      </div>
    </aside>
  )
}
