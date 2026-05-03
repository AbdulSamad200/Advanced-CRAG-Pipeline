// src/components/MessageBubble.jsx
import { User, Bot, ExternalLink, FileText } from 'lucide-react'

// ── URL detector ──────────────────────────────────────────────
function isURL(str) {
  try { return Boolean(new URL(str)) } catch { return false }
}

// ── Inline markdown: bold, italic, inline code ─────────────────
function Inline({ text }) {
  const parts = []
  const re = /(\*\*.*?\*\*|\*.*?\*|`[^`]+`)/g
  let last = 0, m

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    const tok = m[0]
    if (tok.startsWith('**')) {
      parts.push(<strong key={m.index} className="text-white font-semibold">{tok.slice(2, -2)}</strong>)
    } else if (tok.startsWith('*')) {
      parts.push(<em key={m.index} className="italic text-slate-300">{tok.slice(1, -1)}</em>)
    } else {
      parts.push(
        <code key={m.index} className="font-mono text-cyan-300 text-xs bg-void px-1.5 py-0.5 rounded">
          {tok.slice(1, -1)}
        </code>
      )
    }
    last = m.index + tok.length
  }
  if (last < text.length) parts.push(text.slice(last))
  return <>{parts}</>
}

// ── Source line renderer — detects URLs and makes them clickable ─
function SourceLine({ text }) {
  // Pattern: [N] <source> — <description>
  // source can be a URL or a filename
  const match = text.match(/^(\[\d+\])\s+(.+?)(?:\s+—\s+(.*))?$/)
  if (!match) return <span><Inline text={text} /></span>

  const [, badge, source, description] = match
  const url = isURL(source)

  return (
    <span className="flex items-start gap-2 flex-wrap">
      <span className="text-accent font-mono font-bold flex-shrink-0">{badge}</span>
      {url ? (
        <a
          href={source}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 underline underline-offset-2 transition-colors break-all"
        >
          <ExternalLink size={11} className="flex-shrink-0" />
          {source}
        </a>
      ) : (
        <span className="inline-flex items-center gap-1 text-emerald-400 break-all">
          <FileText size={11} className="flex-shrink-0" />
          {source}
        </span>
      )}
      {description && (
        <span className="text-slate-500">— {description}</span>
      )}
    </span>
  )
}

// ── Full markdown renderer ─────────────────────────────────────
function renderMarkdown(text) {
  if (!text) return []
  const lines = text.split('\n')
  const elements = []
  let i = 0
  let inSourcesSection = false

  while (i < lines.length) {
    const line = lines[i]

    // Code block
    if (line.startsWith('```')) {
      const codeLines = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      elements.push(
        <pre key={i} className="bg-void rounded-lg p-3 my-2 overflow-x-auto border border-border">
          <code className="font-mono text-xs text-cyan-300 leading-relaxed">
            {codeLines.join('\n')}
          </code>
        </pre>
      )
      i++; continue
    }

    // Headings
    if (line.startsWith('## Sources') || line.startsWith('## Source')) {
      inSourcesSection = true
      elements.push(
        <p key={i} className="font-display font-bold text-white mt-4 mb-2 flex items-center gap-1.5">
          <ExternalLink size={13} className="text-accent" />
          Sources
        </p>
      )
      i++; continue
    }

    if (line.startsWith('### ')) {
      inSourcesSection = false
      elements.push(<p key={i} className="font-display font-bold text-white text-sm mt-3 mb-1">{line.slice(4)}</p>)
      i++; continue
    }

    if (line.startsWith('## ')) {
      inSourcesSection = false
      elements.push(<p key={i} className="font-display font-bold text-white mb-1">{line.slice(3)}</p>)
      i++; continue
    }

    // Bullet list
    if (line.startsWith('- ') || line.startsWith('* ')) {
      const items = []
      while (i < lines.length && (lines[i].startsWith('- ') || lines[i].startsWith('* '))) {
        items.push(lines[i].slice(2))
        i++
      }
      elements.push(
        <ul key={i} className="space-y-1.5 my-2">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-slate-300">
              {inSourcesSection ? (
                // Source lines in ## Sources section
                <SourceLine text={item} />
              ) : (
                <>
                  <span className="text-accent mt-0.5 flex-shrink-0">▸</span>
                  <span><Inline text={item} /></span>
                </>
              )}
            </li>
          ))}
        </ul>
      )
      continue
    }

    // Numbered list
    if (/^\d+\.\s/.test(line)) {
      const items = []
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s/, ''))
        i++
      }
      elements.push(
        <ol key={i} className="space-y-1.5 my-2">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-slate-300">
              {inSourcesSection ? (
                <SourceLine text={`[${idx + 1}] ${item}`} />
              ) : (
                <>
                  <span className="text-accent/70 font-mono text-xs mt-0.5 flex-shrink-0 w-4">{idx + 1}.</span>
                  <span><Inline text={item} /></span>
                </>
              )}
            </li>
          ))}
        </ol>
      )
      continue
    }

    // Blockquote
    if (line.startsWith('> ')) {
      elements.push(
        <blockquote key={i} className="border-l-2 border-accent/40 pl-3 text-slate-400 italic my-2">
          <Inline text={line.slice(2)} />
        </blockquote>
      )
      i++; continue
    }

    // Divider
    if (line.match(/^─+$/) || line.match(/^-{3,}$/) || line.match(/^={3,}$/)) {
      elements.push(<hr key={i} className="border-border my-3" />)
      i++; continue
    }

    // Empty line
    if (!line.trim()) {
      elements.push(<div key={i} className="h-1.5" />)
      i++; continue
    }

    // Regular paragraph — check if it looks like a source line in sources section
    if (inSourcesSection && line.match(/^\[\d+\]/)) {
      elements.push(
        <div key={i} className="mb-1.5">
          <SourceLine text={line} />
        </div>
      )
      i++; continue
    }

    elements.push(
      <p key={i} className="text-slate-300 leading-relaxed mb-1">
        <Inline text={line} />
      </p>
    )
    i++
  }

  return elements
}

// ── Message bubble ─────────────────────────────────────────────
export default function MessageBubble({ message, isLoading }) {
  const isUser  = message.role === 'user'
  const isEmpty = !message.content && !isUser

  return (
    <div className={`flex gap-3 animate-slide-up ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-xl flex-shrink-0 flex items-center justify-center
        ${isUser ? 'bg-accent/20 border border-accent/30' : 'bg-panel border border-border'}`}
      >
        {isUser
          ? <User size={13} className="text-accent" />
          : <Bot  size={13} className="text-slate-400" />
        }
      </div>

      {/* Bubble */}
      <div className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm
        ${isUser
          ? 'bg-accent/15 border border-accent/25 text-slate-200 rounded-tr-sm'
          : 'bg-panel border border-border text-slate-300 rounded-tl-sm'
        }`}
      >
        {isUser ? (
          <p className="font-body leading-relaxed whitespace-pre-wrap">{message.content}</p>
        ) : isEmpty ? (
          <span className="typing-cursor text-slate-500 text-xs font-mono">Thinking</span>
        ) : (
          <div className="font-body text-sm">
            {renderMarkdown(message.content)}
            {isLoading && <span className="typing-cursor" />}
          </div>
        )}
      </div>
    </div>
  )
}