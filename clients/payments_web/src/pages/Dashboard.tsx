import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Line, Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

type Row = { created_at:string, direction:string, amount_cents:number }
type St = { from:string, to:string, gross_cents:number, fees_cents:number, net_cents:number, rows:Row[] }

export default function DashboardPage() {
  const [data, setData] = useState<St | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [range, setRange] = useState<'7d'|'30d'|'90d'>('30d')
  const load = async () => {
    try {
      const now = new Date()
      const to = now.toISOString()
      const days = range==='7d'?7:range==='30d'?30:90
      const from = new Date(now.getTime() - days*24*3600*1000).toISOString()
      setData(await api.merchantStatementJson({ from, to }))
    } catch(e:any) { setErr(e.message) }
  }
  useEffect(()=>{ load() },[range])

  const chart = useMemo(() => {
    if (!data) return null
    // aggregate per day
    const map = new Map<string, number>()
    const grossMap = new Map<string, number>()
    const feesMap = new Map<string, number>()
    const countMap = new Map<string, number>()
    for (const r of data.rows) {
      const day = r.created_at.slice(0,10)
      const cur = map.get(day) || 0
      const sign = r.direction === 'in' ? 1 : r.direction === 'fee' ? -1 : 0
      map.set(day, cur + sign * r.amount_cents)
      countMap.set(day, (countMap.get(day)||0)+1)
      if (r.direction === 'in') grossMap.set(day, (grossMap.get(day)||0) + r.amount_cents)
      if (r.direction === 'fee') feesMap.set(day, (feesMap.get(day)||0) + r.amount_cents)
    }
    const labels = Array.from(map.keys()).sort()
    const series = labels.map(l => map.get(l) || 0)
    const gross = labels.map(l => grossMap.get(l) || 0)
    const fees = labels.map(l => Math.abs(feesMap.get(l) || 0))
    const counts = labels.map(l => countMap.get(l) || 0)
    return {
      flow: {
        labels,
        datasets: [
          { label: 'Net Flow (cents)', data: series, borderColor: '#4f46e5', backgroundColor: 'rgba(79,70,229,0.2)' },
          { label: 'Gross (cents)', data: gross, borderColor: '#16a34a', backgroundColor: 'rgba(22,163,74,0.2)' },
          { label: 'Fees (cents)', data: fees, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.2)' },
        ]
      },
      counts: {
        labels,
        datasets: [
          { label: 'Transactions', data: counts, backgroundColor: 'rgba(79,70,229,0.6)' }
        ]
      }
    }
  }, [data])

  return (
    <div className="max-w-5xl mx-auto mt-6 grid gap-6">
      <div className="card">
        <h2 className="text-lg font-semibold">Dashboard</h2>
        <div className="mt-2 flex gap-2 items-center text-sm">
          <span className="text-gray-500">Range:</span>
          <button className={`btn ${range==='7d'?'opacity-100':'opacity-70'}`} onClick={()=>setRange('7d')}>7d</button>
          <button className={`btn ${range==='30d'?'opacity-100':'opacity-70'}`} onClick={()=>setRange('30d')}>30d</button>
          <button className={`btn ${range==='90d'?'opacity-100':'opacity-70'}`} onClick={()=>setRange('90d')}>90d</button>
        </div>
        {err && <div className="text-red-600 text-sm mt-2">{err}</div>}
        {data && (
          <div className="grid grid-cols-3 gap-3 text-sm mt-3">
            <div><div className="text-gray-500">Gross</div><div className="text-2xl font-semibold">{data.gross_cents}</div></div>
            <div><div className="text-gray-500">Fees</div><div className="text-2xl font-semibold">{data.fees_cents}</div></div>
            <div><div className="text-gray-500">Net</div><div className="text-2xl font-semibold">{data.net_cents}</div></div>
          </div>
        )}
      </div>
      <div className="card">
        <h3 className="font-semibold mb-2">Gross / Net / Fees (daily)</h3>
        {chart ? <Line data={(chart as any).flow} /> : <div className="text-sm">Loading…</div>}
      </div>
      <div className="card">
        <h3 className="font-semibold mb-2">Daily Transaction Count</h3>
        {chart ? <Bar data={(chart as any).counts} /> : <div className="text-sm">Loading…</div>}
      </div>
    </div>
  )
}
