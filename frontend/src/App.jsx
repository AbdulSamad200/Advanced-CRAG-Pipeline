// src/App.jsx
import { useState, useCallback, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar.jsx'
import ChatWindow from './components/ChatWindow.jsx'
import LogPanel from './components/LogPanel.jsx'
import { streamChat, fetchHealth } from './api/ragApi.js'

let _convCounter = 0
const makeConvId = () => `conv-${++_convCounter}`
const makeMsgId  = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`

function newConversation(title = 'New chat') {
  return { id: makeConvId(), title, messages: [], createdAt: Date.now() }
}

export default function App() {
  const [conversations, setConversations] = useState(() => [newConversation()])
  const [activeId,      setActiveId]      = useState(() => conversations[0].id)
  const [logs,          setLogs]          = useState([])
  const [isLoading,     setIsLoading]     = useState(false)
  const [logOpen,       setLogOpen]       = useState(true)
  const [health,        setHealth]        = useState(null)

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: 'error', rag_ready: false }))
  }, [])

  const activeConv = conversations.find(c => c.id === activeId) ?? conversations[0]

  const updateConv = useCallback((id, updater) => {
    setConversations(prev => prev.map(c => c.id === id ? updater(c) : c))
  }, [])

  const addMessage = useCallback((convId, role, content) => {
    updateConv(convId, c => ({
      ...c,
      title: c.messages.length === 0 && role === 'user'
        ? content.slice(0, 42) + (content.length > 42 ? '…' : '')
        : c.title,
      messages: [...c.messages, { id: makeMsgId(), role, content, ts: Date.now() }],
    }))
  }, [updateConv])

  // Append a text chunk to the last assistant message
  const appendChunk = useCallback((convId, chunk) => {
    setConversations(prev => prev.map(c => {
      if (c.id !== convId) return c
      const msgs = [...c.messages]
      if (msgs.length && msgs[msgs.length - 1].role === 'assistant') {
        const last = msgs[msgs.length - 1]
        msgs[msgs.length - 1] = { ...last, content: last.content + chunk }
      }
      return { ...c, messages: msgs }
    }))
  }, [])

  const handleSend = useCallback(async (query) => {
    if (!query.trim() || isLoading) return

    const targetId = activeId
    setIsLoading(true)
    setLogs([])

    addMessage(targetId, 'user', query)
    addMessage(targetId, 'assistant', '')   // empty placeholder for streaming

    await streamChat({
      query,
      sessionId: targetId,
      onLog: (msg) => {
        setLogs(prev => [...prev, { id: Date.now() + Math.random(), text: msg, ts: Date.now() }])
      },
      onChunk: (chunk) => {
        appendChunk(targetId, chunk)         // append each token as it arrives
      },
      onError: (msg) => {
        appendChunk(targetId, `\n\n❌ Error: ${msg}`)
        setLogs(prev => [...prev, { id: Date.now(), text: `ERROR: ${msg}`, ts: Date.now(), isError: true }])
        setIsLoading(false)
      },
      onDone: () => {
        setIsLoading(false)
      },
    })
  }, [activeId, isLoading, addMessage, appendChunk])

  const handleNewChat = () => {
    const conv = newConversation()
    setConversations(prev => [conv, ...prev])
    setActiveId(conv.id)
    setLogs([])
  }

  const handleSelectConv = (id) => {
    setActiveId(id)
    setLogs([])
  }

  const handleDeleteConv = (id) => {
    setConversations(prev => {
      const next = prev.filter(c => c.id !== id)
      if (next.length === 0) {
        const fresh = newConversation()
        setTimeout(() => setActiveId(fresh.id), 0)
        return [fresh]
      }
      if (id === activeId) setActiveId(next[0].id)
      return next
    })
  }

  return (
    <div className="flex h-full bg-void dot-grid overflow-hidden">
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full bg-accent/5 blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 rounded-full bg-cyan/5 blur-3xl" />
      </div>

      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelectConv}
        onNew={handleNewChat}
        onDelete={handleDeleteConv}
        health={health}
      />

      <main className="flex-1 flex flex-col min-w-0 relative z-10">
        <ChatWindow
          conversation={activeConv}
          isLoading={isLoading}
          onSend={handleSend}
          logOpen={logOpen}
          onToggleLogs={() => setLogOpen(v => !v)}
          logCount={logs.length}
        />
      </main>

      {logOpen && (
        <LogPanel
          logs={logs}
          isLoading={isLoading}
          onClose={() => setLogOpen(false)}
        />
      )}
    </div>
  )
}