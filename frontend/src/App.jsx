import React, { useState } from 'react'
import ModelViewer from './components/ModelViewer'

export default function App() {
  const [files, setFiles] = useState([])
  const [status, setStatus] = useState('idle')
  const [jobId, setJobId] = useState(null)
  const [modelUrl, setModelUrl] = useState(null)
  const [log, setLog] = useState([])

  const pushLog = (line) => setLog(l => [...l, line])

  const onFileChange = (e) => {
    setFiles(Array.from(e.target.files || []))
  }

  const upload = async () => {
    if (!files.length) return
    setStatus('uploading')
    pushLog(`Uploading ${files.length} image(s) ...`)

    const form = new FormData()
    files.forEach(f => form.append('files', f))

    const res = await fetch('/api/upload', { method: 'POST', body: form })
    if (!res.ok) { setStatus('error'); pushLog('Upload failed'); return }
    const { session_id } = await res.json()
    pushLog(`Upload complete. Session: ${session_id}`)

    setStatus('processing')
    pushLog('Starting reconstruction ...')

    const start = await fetch('/api/process', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id }) })
    const data = await start.json()
    setJobId(data.job_id)

    // poll
    const timer = setInterval(async () => {
      const r = await fetch(`/api/status?job_id=${data.job_id}`)
      const s = await r.json()
      if (s.status === 'done') {
        clearInterval(timer)
        setStatus('done')
        pushLog('Reconstruction complete!')
        setModelUrl(`/api/model?job_id=${data.job_id}`)
      } else if (s.status === 'error') {
        clearInterval(timer)
        setStatus('error')
        pushLog('Reconstruction error: ' + (s.error || 'unknown'))
      } else {
        setStatus('processing')
      }
    }, 1500)
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
