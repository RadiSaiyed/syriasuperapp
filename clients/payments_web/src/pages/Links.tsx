import { useState } from 'react'
import { api } from '../api'

export default function LinksPage() {
  const [amount, setAmount] = useState<number | ''>('')
  const [expires, setExpires] = useState<number | ''>('')
  const [code, setCode] = useState<string>('')
  const [payAmount, setPayAmount] = useState<number | ''>('')
  const [result, setResult] = useState<string>('')
  const [err, setErr] = useState<string| null>(null)

  const create = async () => {
    setErr(null); setResult('')
    try {
      const res = await api.createLink(amount === '' ? null : Number(amount), expires === '' ? undefined : Number(expires))
      setCode(res.code)
      setResult('Link created')
    } catch (e:any) { setErr(e.message) }
  }
  const pay = async () => {
    setErr(null); setResult('')
    try {
      const idem = `web-link-${Date.now()}`
      const res = await api.payLink(code, idem, payAmount === '' ? undefined : Number(payAmount))
      setResult(`Paid: ${res.status}`)
    } catch (e:any) { setErr(e.message) }
  }

  return (
    <div className="max-w-3xl mx-auto mt-6 grid gap-6">
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Create Link</h2>
        <div className="grid gap-2">
          <label className="text-sm">Amount (leave empty for static link)</label>
          <input className="input w-60" type="number" value={amount} onChange={e=>setAmount(e.target.value===''? '': Number(e.target.value))} />
          <label className="text-sm">Expires in minutes (optional)</label>
          <input className="input w-60" type="number" value={expires} onChange={e=>setExpires(e.target.value===''? '': Number(e.target.value))} />
          <button className="btn w-40" onClick={create}>Create</button>
          {code && <div className="text-sm break-all">Code: {code}</div>}
        </div>
      </div>
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Pay Link</h2>
        <div className="grid gap-2">
          <label className="text-sm">Code (LINK:v1;code=...)</label>
          <input className="input" value={code} onChange={e=>setCode(e.target.value)} />
          <label className="text-sm">Amount (required for static)</label>
          <input className="input w-60" type="number" value={payAmount} onChange={e=>setPayAmount(e.target.value===''? '': Number(e.target.value))} />
          <button className="btn w-40" onClick={pay} disabled={!code}>Pay</button>
          {result && <div className="text-green-700 text-sm">{result}</div>}
          {err && <div className="text-red-600 text-sm">{err}</div>}
        </div>
      </div>
    </div>
  )
}

