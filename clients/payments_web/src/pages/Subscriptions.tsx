import { useEffect, useState } from 'react'
import { api } from '../api'

type Sub = { id:string, merchant_user_id:string, amount_cents:number, interval_days:number, status:string, next_charge_at:string }

export default function SubscriptionsPage() {
  const [rows, setRows] = useState<Sub[]>([])
  const [merchantPhone, setMerchantPhone] = useState('')
  const [amount, setAmount] = useState(2000)
  const [interval, setInterval] = useState(30)
  const [msg, setMsg] = useState<string>('')
  const [err, setErr] = useState<string | null>(null)

  const load = async () => {
    setErr(null)
    try { setRows(await api.listSubscriptions()) } catch (e:any) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])

  const create = async () => {
    setErr(null); setMsg('')
    try {
      await api.createSubscription(merchantPhone, amount, interval)
      setMsg('Subscription created')
      await load()
    } catch (e:any) { setErr(e.message) }
  }
  const cancel = async (id: string) => {
    setErr(null); setMsg('')
    try { await api.cancelSubscription(id); await load() } catch (e:any) { setErr(e.message) }
  }
  const forceDue = async (id: string) => {
    setErr(null); setMsg('')
    try { await api.forceDueDev(id); await api.processDueDev(); await load(); setMsg('Charged due (dev)') } catch (e:any) { setErr(e.message) }
  }

  return (
    <div className="max-w-4xl mx-auto mt-6 grid gap-6">
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Create Subscription</h2>
        <div className="grid gap-2">
          <label className="text-sm">Merchant phone</label>
          <input className="input w-80" placeholder="+9639..." value={merchantPhone} onChange={e=>setMerchantPhone(e.target.value)} />
          <div className="flex gap-3">
            <div>
              <label className="block text-sm">Amount (cents)</label>
              <input className="input w-48" type="number" value={amount} onChange={e=>setAmount(Number(e.target.value))} />
            </div>
            <div>
              <label className="block text-sm">Interval (days)</label>
              <input className="input w-32" type="number" value={interval} onChange={e=>setInterval(Number(e.target.value))} />
            </div>
          </div>
          <button className="btn w-40" onClick={create}>Create</button>
          {msg && <div className="text-green-700 text-sm">{msg}</div>}
          {err && <div className="text-red-600 text-sm">{err}</div>}
        </div>
      </div>
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Your Subscriptions</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left border-b"><th>ID</th><th>Amount</th><th>Interval</th><th>Status</th><th>Next</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-b">
                  <td className="py-2 pr-3">{r.id.slice(0,8)}…</td>
                  <td className="pr-3">{r.amount_cents}</td>
                  <td className="pr-3">{r.interval_days}d</td>
                  <td className="pr-3">{r.status}</td>
                  <td className="pr-3">{r.next_charge_at}</td>
                  <td className="pr-3 flex gap-2">
                    <button className="btn" onClick={()=>cancel(r.id)} disabled={r.status!=='active'}>Cancel</button>
                    <button className="btn" onClick={()=>forceDue(r.id)}>Dev charge</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

