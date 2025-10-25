import { useEffect, useState } from 'react'
import { api } from '../api'
import * as XLSX from 'xlsx'

type St = { from:string, to:string, gross_cents:number, fees_cents:number, net_cents:number, rows:any[] }

export default function StatementPage() {
  const [data, setData] = useState<St | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [from, setFrom] = useState<string>('')
  const [to, setTo] = useState<string>('')

  const load = async () => {
    setErr(null)
    try { setData(await api.merchantStatementJson({ from: from || undefined, to: to || undefined })) } catch (e:any) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])

  const downloadCsv = async () => {
    try {
      const csv = await api.merchantStatementCsv({ from, to })
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'statement.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e:any) { setErr(e.message) }
  }
  const downloadXlsx = async () => {
    if (!data) return
    const ws = XLSX.utils.json_to_sheet(data.rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Statement')
    XLSX.writeFile(wb, 'statement.xlsx')
  }

  return (
    <div className="max-w-4xl mx-auto mt-6 grid gap-6">
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Statement</h2>
        <div className="flex gap-3 items-end">
          <div>
            <label className="block text-sm">From (ISO)</label>
            <input className="input w-64" placeholder="2025-09-01T00:00:00Z" value={from} onChange={e=>setFrom(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm">To (ISO)</label>
            <input className="input w-64" placeholder="2025-09-30T23:59:59Z" value={to} onChange={e=>setTo(e.target.value)} />
          </div>
          <button className="btn" onClick={load}>Refresh</button>
          <button className="btn" onClick={downloadCsv}>Download CSV</button>
          <button className="btn" onClick={downloadXlsx} disabled={!data}>Download XLSX</button>
        </div>
        {err && <div className="text-red-600 text-sm mt-2">{err}</div>}
      </div>
      {data && (
        <div className="card">
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div><div className="text-gray-500">Gross</div><div className="text-lg font-semibold">{data.gross_cents}</div></div>
            <div><div className="text-gray-500">Fees</div><div className="text-lg font-semibold">{data.fees_cents}</div></div>
            <div><div className="text-gray-500">Net</div><div className="text-lg font-semibold">{data.net_cents}</div></div>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b"><th>Date</th><th>Dir</th><th>Amount</th><th>Curr</th><th>ID</th></tr>
              </thead>
              <tbody>
                {data.rows.map((r:any, idx:number) => (
                  <tr key={idx} className="border-b">
                    <td className="py-1 pr-3">{r.created_at}</td>
                    <td className="pr-3">{r.direction}</td>
                    <td className="pr-3">{r.amount_cents}</td>
                    <td className="pr-3">{r.currency_code}</td>
                    <td className="pr-3">{r.transfer_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
