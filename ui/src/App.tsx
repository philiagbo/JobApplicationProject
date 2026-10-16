import { useEffect, useState } from 'react'

export default function App() {
  const [status, setStatus] = useState<'checking' | 'ok' | 'down'>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d: { ok: boolean }) => setStatus(d.ok ? 'ok' : 'down'))
      .catch(() => setStatus('down'))
  }, [])

  return (
    <main style={{ padding: 24 }}>
      <h1>Job Helper</h1>
      {status === 'checking' && <p style={{ color: 'var(--muted)' }}>Checking API…</p>}
      {status === 'ok' && <p style={{ color: 'var(--ok)' }}>API connected</p>}
      {status === 'down' && <p style={{ color: 'var(--bad)' }}>API not reachable. Is Flask running?</p>}
    </main>
  )
}
