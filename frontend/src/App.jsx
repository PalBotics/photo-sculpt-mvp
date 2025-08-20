import React, { useRef, useState } from 'react'
import ModelViewer from './components/ModelViewer'

export default function App() {
  const [files, setFiles] = useState([])
  const [status, setStatus] = useState('idle')
  const [jobId, setJobId] = useState(null)
  const [modelUrl, setModelUrl] = useState(null)
  const [log, setLog] = useState([])
  const [progress, setProgress] = useState(0)
  const [step, setStep] = useState('idle')

  const lastLogCountRef = useRef(0)
  const pollRef = useRef(null)

  const pushLog = (line) => setLog(l => [...l, line])

  const onFileChange = (e) => {
    setFiles(Array.from(e.target.files || []))
  }

  const upload = async () => {
    if (!files.length) return
    setStatus('uploading')
    setProgress(0)
    setStep('uploading images')
    setLog([])
    lastLogCountRef.current = 0
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }

    pushLog(`Uploading ${files.length} image(s) ...`)

    const form = new FormData()
    files.forEach(f => form.append('files', f))

    const res = await fetch('/api/upload', { method: 'POST', body: form })
    if (!res.ok) { setStatus('error'); pushLog('Upload failed'); return }
    const { session_id } = await res.json()
    if (!session_id) { setStatus('error'); pushLog('Upload did not return a session_id'); return }
    pushLog(`Upload complete. Session: ${session_id}`)

    setStatus('processing')
    setStep('queued')
    pushLog('Starting reconstruction ...')

    const startRes = await fetch('/api/process', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id }) })
    if (!startRes.ok) {
      const text = await startRes.text()
      setStatus('error')
      pushLog('Process start failed: ' + text)
      return
    }
    const data = await startRes.json()
    if (!data.job_id) {
      setStatus('error')
      pushLog('Process start did not return a job_id')
      return
    }
    setJobId(data.job_id)

    // poll
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`/api/status?job_id=${data.job_id}`)
        if (!r.ok) throw new Error(`status ${r.status}`)
        const s = await r.json()

        // Append any new backend log lines
        if (Array.isArray(s.log)) {
          const startIdx = lastLogCountRef.current || 0
          const newLines = s.log.slice(startIdx)
          if (newLines.length) {
            setLog(l => [...l, ...newLines])
            lastLogCountRef.current = s.log.length
          }
        }

        if (typeof s.progress === 'number') setProgress(Math.max(0, Math.min(100, s.progress)))
        if (s.step) setStep(s.step)
        if (s.status) setStatus(s.status)

        if (s.status === 'done') {
          clearInterval(pollRef.current)
          pollRef.current = null
          pushLog('Reconstruction complete!')
          setModelUrl(`/api/model?job_id=${data.job_id}`)
        } else if (s.status === 'error') {
          clearInterval(pollRef.current)
          pollRef.current = null
          pushLog('Reconstruction error: ' + (s.error || 'unknown'))
        }
      } catch (err) {
        clearInterval(pollRef.current)
        pollRef.current = null
        setStatus('error')
        pushLog('Status polling failed: ' + err.message)
      }
    }, 1000)
  }

  return (
    <div style={{ fontFamily: 'ui-sans-serif, system-ui, -apple-system', padding: 24, maxWidth: 1000, margin: '0 auto' }}>
      <h1 style={{ fontSize: 28, marginBottom: 8 }}>Photo Sculpt — MVP</h1>
      <p style={{ opacity: 0.8, marginBottom: 16 }}>Upload multiple images of your object and generate a quick 3D preview.</p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <div>
          <div style={{ border: '2px dashed #d0d0d0', padding: 16, borderRadius: 12, background: '#fafafa' }}>
            <input type="file" accept="image/*" multiple onChange={onFileChange} />
            <button onClick={upload} disabled={!files.length || status==='uploading' || status==='processing'} style={{ marginLeft: 12, padding: '8px 12px', borderRadius: 10, border: '1px solid #ddd', background: '#fff', cursor: 'pointer' }}>Process</button>
            <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
              {files.length ? `${files.length} selected` : 'No files selected'}
            </div>
          </div>

          {/* Progress */}
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <div style={{ fontSize: 12, color: '#444' }}>{step}</div>
              <div style={{ fontSize: 12, color: '#666' }}>{progress}%</div>
            </div>
            <div style={{ height: 10, background: '#eee', borderRadius: 999, overflow: 'hidden', boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.05)' }}>
              <div style={{ width: `${progress}%`, height: '100%', background: '#4f46e5', transition: 'width 300ms ease' }} />
            </div>
          </div>

          {/* Log */}
          <div style={{ marginTop: 16 }}>
            <h3 style={{ margin: '8px 0' }}>Log</h3>
            <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', background: '#0b1021', color: '#d7e0ff', padding: 12, borderRadius: 8, height: 180, overflow: 'auto' }}>
              {log.map((l, i) => <div key={i}>$ {l}</div>)}
            </div>
          </div>
        </div>

        <div>
          <ModelViewer url={modelUrl} />
          <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>Status: {status}</div>
        </div>
      </div>
    </div>
  )
}
