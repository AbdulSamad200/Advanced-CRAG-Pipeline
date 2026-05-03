// src/components/ChatWindow.jsx
import { useState, useRef, useEffect } from 'react'
import { Send, PanelRight, PanelRightOpen, Loader2, Bot } from 'lucide-react'
import MessageBubble from './MessageBubble.jsx'

function EmptyState() {
  const prompts = [
    'What are the key findings in the uploaded documents?',
    'Summarize the main topics covered in the knowledge base.',
    'Tell me about the latest AI research trends.',
    'What does the document say about neural networks?',
  ]
  return (
    <div className="flex flex-col items-center justify-center h-full px-8 text-center">
      <div className="w-14 h-14 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center mb-4">
        <Bot size={24} className="text-accent" />
      </div>
      <h2 className="text-xl font-display font-bold text-white mb-1">Research Assistant</h2>
      <p className="text-sm text-slate-500 font-body mb-8 max-w-xs">
        Ask anything — I'll search your PDFs first, then fall back to the web using the CRAG pipeline.
      </p>
      <div className="grid grid-cols-1 gap-2 w-full max-w-sm">
        {prompts.map((p, i) => (
          <button
            key={i}
            onClick={() => document.getElementById('chat-input')?.dispatchEvent(
              new CustomEvent('suggestion', { detail: p, bubbles: true })
            )}
            className="text-left px-4 py-2.5 rounded-xl bg-panel border border-border hover:border-accent/30 hover:bg-accent/5 transition-all duration-150 text-xs text-slate-400 hover:text-slate-200 font-body"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function ChatWindow({ conversation, isLoading, onSend, logOpen, onToggleLogs, logCount }) {
  const [input, setInput] = useState('')
  const bottomRef  = useRef()
  const inputRef   = useRef()
  const messagesRef = useRef()

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation?.messages])

  // Handle suggestion clicks from EmptyState
  useEffect(() => {
    const handler = (e) => {
      setInput(e.detail)
      inputRef.current?.focus()
    }
    document.getElementById('chat-input')?.addEventListener('suggestion', handler)
    return () => document.getElementById('chat-input')?.removeEventListener('suggestion', handler)
  }, [])

  const handleSubmit = () => {
    const q = input.trim()
    if (!q || isLoading) return
    setInput('')
    onSend(q)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const msgs = conversation?.messages ?? []

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ───────────────────────────────────────────── */}
      <header className="flex-shrink-0 flex items-center justify-between px-5 py-3.5 border-b border-border/50 bg-deep/60 backdrop-blur-sm">
        <div className="min-w-0">
          <h2 className="text-sm font-display font-bold text-white truncate">
            {conversation?.title || 'New conversation'}
          </h2>
          <p className="text-xs text-slate-600 font-mono">
            {msgs.filter(m => m.role === 'user').length} messages
          </p>
        </div>
        <button
          onClick={onToggleLogs}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-body transition-all duration-150
            ${logOpen
              ? 'bg-accent/15 text-accent border border-accent/25'
              : 'bg-panel text-slate-500 hover:text-slate-300 border border-border hover:border-muted'
            }`}
        >
          {logOpen ? <PanelRight size={13} /> : <PanelRightOpen size={13} />}
          {logOpen ? 'Hide' : 'Show'} logs
          {logCount > 0 && (
            <span className="bg-accent/20 text-accent rounded-full px-1.5 py-0.5 text-xs font-mono">
              {logCount}
            </span>
          )}
        </button>
      </header>

      {/* ── Messages ─────────────────────────────────────────── */}
      <div ref={messagesRef} className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        {msgs.length === 0 ? (
          <EmptyState />
        ) : (
          msgs.map(msg => (
            <MessageBubble key={msg.id} message={msg} isLoading={isLoading && msg === msgs[msgs.length - 1]} />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input area ───────────────────────────────────────── */}
      <div className="flex-shrink-0 px-4 pb-5 pt-2">
        <div className={`flex items-end gap-3 rounded-2xl border transition-all duration-200 p-3
          ${isLoading
            ? 'border-accent/30 bg-accent/5'
            : 'border-border bg-surface hover:border-muted focus-within:border-accent/50 focus-within:bg-panel/50'
          }`}
        >
          <textarea
            id="chat-input"
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isLoading ? 'Processing your query...' : 'Ask anything about your documents or any topic…'}
            disabled={isLoading}
            rows={1}
            className="flex-1 bg-transparent resize-none outline-none text-sm font-body text-slate-200 placeholder:text-slate-600
              disabled:opacity-50 min-h-[24px] max-h-40 overflow-y-auto leading-6"
            style={{ height: 'auto' }}
            onInput={e => {
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px'
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || isLoading}
            className={`flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150
              ${!input.trim() || isLoading
                ? 'bg-muted/50 text-slate-600 cursor-not-allowed'
                : 'bg-accent hover:bg-accent/80 text-white shadow-lg shadow-accent/25 hover:shadow-accent/40'
              }`}
          >
            {isLoading
              ? <Loader2 size={14} className="animate-spin" />
              : <Send size={14} />
            }
          </button>
        </div>
        <p className="text-center text-xs text-slate-700 font-mono mt-2">
          CRAG pipeline · Gemini 2.5 Flash · Qdrant · Tavily
        </p>
      </div>
    </div>
  )
}
