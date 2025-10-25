import { useEffect, useMemo, useState } from 'react'

type Endpoint = { id:string, url:string, active:boolean, created_at?:string }
type Delivery = { id:string, endpoint_id:string, event_type:string, status:string, attempt_count:number, created_at:string }

async function http<T>(path: string, opts: RequestInit = {}) {
  const BASE = (import.meta as any).env.VITE_API_BASE || 'http://localhost:8080'
  const headers: any = { 'Content-Type':'application/json', ...(opts.headers||{}) }
  const tok = localStorage.getItem('token'); if (tok) headers['Authorization'] = `Bearer ${tok}`
  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
  if (!res.ok) throw new Error(`${res.status}`)
  return await res.json() as T
}

export default function WebhooksPage() {
  const [eps, setEps] = useState<Endpoint[]>([])
  const [url, setUrl] = useState('app://echo')
  const [secret, setSecret] = useState('whsec_dev')
  const [deliveries, setDeliveries] = useState<Delivery[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [eventFilter, setEventFilter] = useState<string>('')
  const [auto, setAuto] = useState<boolean>(false)
  const [intervalMs, setIntervalMs] = useState<number>(5000)
  // Verify block
  const [vTs, setVTs] = useState('')
  const [vEvent, setVEvent] = useState('')
  const [vBody, setVBody] = useState('')
  const [vSecret, setVSecret] = useState('')
  const [vSign, setVSign] = useState('')
  const [vExpected, setVExpected] = useState('')

  const load = async () => {
    setErr(null)
    try {
      const e = await http<Endpoint[]>(`/webhooks/endpoints`)
      setEps(e)
      const d = await http<Delivery[]>(`/webhooks/deliveries`)
      setDeliveries(d)
    } catch (e:any) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (!auto) return
    const id = setInterval(load, intervalMs)
    return () => clearInterval(id)
  }, [auto, intervalMs])

  const filtered = useMemo(() => {
    return deliveries.filter(d => (
      (!statusFilter || d.status === statusFilter) && (!eventFilter || d.event_type.toLowerCase().includes(eventFilter.toLowerCase()))
    ))
  }, [deliveries, statusFilter, eventFilter])

  const create = async () => {
    setErr(null)
    try { await http(`/webhooks/endpoints?url=${encodeURIComponent(url)}&secret=${encodeURIComponent(secret)}`, { method:'POST' }); await load() } catch (e:any) { setErr(e.message) }
  }
  const sendTest = async () => {
    setErr(null)
    try { await http(`/webhooks/test`, { method:'POST' }); await load() } catch (e:any) { setErr(e.message) }
  }
  const requeue = async (id: string) => {
    setErr(null)
    try { await http(`/webhooks/deliveries/${id}/requeue`, { method:'POST' }); await load() } catch (e:any) { setErr(e.message) }
  }

  return (
    <div className="max-w-5xl mx-auto mt-6 grid gap-6">
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Create Endpoint</h2>
        <div className="flex gap-3 items-end">
          <div>
            <label className="block text-sm">URL</label>
            <input className="input w-96" placeholder="https://example.com/webhook" value={url} onChange={e=>setUrl(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm">Secret</label>
            <input className="input w-60" value={secret} onChange={e=>setSecret(e.target.value)} />
          </div>
          <button className="btn" onClick={create}>Create</button>
          <button className="btn" onClick={sendTest} disabled={eps.length===0}>Send Test</button>
        </div>
        {err && <div className="text-red-600 text-sm mt-2">{err}</div>}
      </div>
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Endpoints</h2>
        <ul className="list-disc ml-5 text-sm">
          {eps.map(e => <li key={e.id} className="mb-1">{e.url} <span className="text-gray-500">({e.active? 'active':'inactive'})</span></li>)}
        </ul>
      </div>
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Deliveries</h2>
        <div className="flex gap-3 items-end mb-2">
          <div>
            <label className="block text-sm">Status</label>
            <select className="input w-48" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}>
              <option value="">All</option>
              <option value="pending">pending</option>
              <option value="delivered">delivered</option>
              <option value="failed">failed</option>
            </select>
          </div>
          <div>
            <label className="block text-sm">Event contains</label>
            <input className="input w-64" value={eventFilter} onChange={e=>setEventFilter(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm">Auto refresh</label>
            <input type="checkbox" checked={auto} onChange={e=>setAuto(e.target.checked)} />
          </div>
          <div>
            <label className="block text-sm">Interval (ms)</label>
            <input className="input w-32" type="number" value={intervalMs} onChange={e=>setIntervalMs(Number(e.target.value)||5000)} />
          </div>
          <button className="btn" onClick={load}>Refresh</button>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead><tr className="text-left border-b"><th>ID</th><th>Event</th><th>Status</th><th>Attempts</th><th>Created</th><th>Actions</th></tr></thead>
            <tbody>
              {filtered.map(d => (
                <tr key={d.id} className="border-b">
                  <td className="py-1 pr-3">{d.id.slice(0,8)}…</td>
                  <td className="pr-3">{d.event_type}</td>
                  <td className="pr-3">{d.status}</td>
                  <td className="pr-3">{d.attempt_count}</td>
                  <td className="pr-3">{d.created_at}</td>
                  <td className="pr-3"><button className="btn" onClick={()=>requeue(d.id)}>Requeue</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Verify Signature</h2>
        <div className="grid gap-2">
          <label className="text-sm">X-Webhook-Ts</label>
          <input className="input" value={vTs} onChange={e=>setVTs(e.target.value)} />
          <label className="text-sm">X-Webhook-Event</label>
          <input className="input" value={vEvent} onChange={e=>setVEvent(e.target.value)} />
          <label className="text-sm">Body JSON</label>
          <textarea className="input" rows={4} value={vBody} onChange={e=>setVBody(e.target.value)} />
          <label className="text-sm">Secret</label>
          <input className="input" value={vSecret} onChange={e=>setVSecret(e.target.value)} />
          <label className="text-sm">X-Webhook-Sign</label>
          <input className="input" value={vSign} onChange={e=>setVSign(e.target.value)} />
          <button className="btn w-40" onClick={() => {
            try {
              // Normalize body to minified JSON similar to backend
              const bodyMin = vBody.trim().startsWith('{') ? JSON.stringify(JSON.parse(vBody)) : vBody
              // compute
              import('../utils/hmac').then(({ computeWebhookSign }) => {
                const exp = computeWebhookSign(vSecret, vTs, vEvent, bodyMin)
                setVExpected(exp)
              })
            } catch (e) { setVExpected('') }
          }}>Compute</button>
          {vExpected && (
            <div className="text-sm">
              Expected: <code className="break-all">{vExpected}</code><br/>
              {vSign ? (
                <span className={vExpected===vSign ? 'text-green-600' : 'text-red-600'}>
                  {vExpected===vSign ? 'Match' : 'Mismatch'}
                </span>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
