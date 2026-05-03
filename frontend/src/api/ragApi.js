// src/api/ragApi.js

const BASE = '/api'

/**
 * Stream a chat query via SSE.
 *
 * Events fired:
 *   onLog(message)      — pipeline log line
 *   onChunk(text)       — streaming token chunk from Gemini
 *   onDone()            — stream complete
 *   onError(message)    — error
 */
export async function streamChat({ query, sessionId = '', onLog, onChunk, onDone, onError }) {
  let response
  try {
    response = await fetch(`${BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, session_id: sessionId }),
    })
  } catch (err) {
    onError?.(`Network error: ${err.message}`)
    return
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: 'Unknown error' }))
    onError?.(detail.detail || `HTTP ${response.status}`)
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE events are separated by \n\n
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''   // keep the incomplete last chunk

      for (const part of parts) {
        for (const line of part.split('\n')) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const raw = trimmed.slice(6).trim()
          if (!raw) continue

          try {
            const event = JSON.parse(raw)
            switch (event.type) {
              case 'log':
                onLog?.(event.message)
                break
              case 'chunk':
                onChunk?.(event.content)   // ← streaming token
                break
              case 'error':
                onError?.(event.message)
                break
              case 'done':
                onDone?.()
                break
            }
          } catch {
            // malformed JSON — skip
          }
        }
      }
    }
  } finally {
    reader.cancel()
  }
}

export async function uploadPDF(file, onProgress) {
  const form = new FormData()
  form.append('file', file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/upload-pdf`)

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100))
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        try {
          reject(new Error(JSON.parse(xhr.responseText).detail || `HTTP ${xhr.status}`))
        } catch {
          reject(new Error(`HTTP ${xhr.status}`))
        }
      }
    })

    xhr.addEventListener('error', () => reject(new Error('Upload failed — network error')))
    xhr.send(form)
  })
}

export async function listPDFs() {
  const res = await fetch(`${BASE}/pdfs`)
  if (!res.ok) throw new Error('Failed to fetch PDF list')
  return res.json()
}

export async function fetchHealth() {
  const res = await fetch(`${BASE}/health`)
  return res.json()
}