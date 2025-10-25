import { useEffect, useState } from 'react'
import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import { api } from './api'
import { getToken, setToken, clearToken } from './auth'
import QRCode from 'qrcode.react'
import LinksPage from './pages/Links'
import SubscriptionsPage from './pages/Subscriptions'
import StatementPage from './pages/Statement'
import QRPayPage from './pages/QRPay'
import WebhooksPage from './pages/Webhooks'
import DashboardPage from './pages/Dashboard'

function Nav() {
  const nav = useNavigate()
  const [dark, setDark] = useState<boolean>(false)
  useEffect(()=>{
    const pref = localStorage.getItem('theme')
    const isDark = pref ? pref === 'dark' : false
    setDark(isDark)
    document.documentElement.classList.toggle('dark', isDark)
  },[])
  const toggleTheme = () => {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle('dark', next)
    localStorage.setItem('theme', next ? 'dark' : 'light')
  }
  const onLogout = () => { clearToken(); nav('/login') }
  return (
    <div className="bg-white shadow">
      <div className="max-w-4xl mx-auto px-4 py-3 flex gap-4 items-center">
        <Link to="/" className="font-semibold">Payments</Link>
        <Link to="/wallet" className="text-gray-600 hover:text-gray-900">Wallet</Link>
        <Link to="/transfer" className="text-gray-600 hover:text-gray-900">P2P</Link>
        <Link to="/merchant" className="text-gray-600 hover:text-gray-900">Merchant</Link>
        <Link to="/links" className="text-gray-600 hover:text-gray-900">Links</Link>
        <Link to="/subs" className="text-gray-600 hover:text-gray-900">Subs</Link>
        <Link to="/statement" className="text-gray-600 hover:text-gray-900">Statement</Link>
        <Link to="/qrpay" className="text-gray-600 hover:text-gray-900">QR Pay</Link>
        <Link to="/webhooks" className="text-gray-600 hover:text-gray-900">Webhooks</Link>
        <Link to="/dashboard" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
        <div className="flex-1" />
        <button className="btn" onClick={toggleTheme}>{dark? 'Light' : 'Dark'}</button>
        <button className="btn" onClick={onLogout}>Logout</button>
      </div>
    </div>
  )
}

function Login() {
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [otp, setOtp] = useState('')
  const [err, setErr] = useState<string|null>(null)
  const nav = useNavigate()
  const request = async () => {
    setErr(null)
    try { await api.requestOtp(phone); setOtpSent(true) } catch (e:any) { setErr(e.message) }
  }
  const verify = async () => {
    setErr(null)
    try {
      const res = await api.verifyOtp(phone, otp || '123456', name || 'Web User')
      setToken(res.access_token)
      nav('/wallet')
    } catch (e:any) { setErr(e.message) }
  }
  return (
    <div className="max-w-md mx-auto mt-10 card">
      <h1 className="text-xl font-semibold mb-4">Login</h1>
      <label className="block text-sm mb-1">Phone</label>
      <input className="input mb-3" placeholder="+9639..." value={phone} onChange={e=>setPhone(e.target.value)} />
      {!otpSent && <button className="btn w-full" onClick={request} disabled={!phone}>Get OTP</button>}
      {otpSent && (
        <div className="mt-3">
          <label className="block text-sm mb-1">Name</label>
          <input className="input mb-2" placeholder="Your name" value={name} onChange={e=>setName(e.target.value)} />
          <label className="block text-sm mb-1">OTP (dev: 123456)</label>
          <input className="input mb-3" placeholder="123456" value={otp} onChange={e=>setOtp(e.target.value)} />
          <button className="btn w-full" onClick={verify}>Login</button>
        </div>
      )}
      {err && <p className="text-red-600 mt-3 text-sm">{err}</p>}
    </div>
  )
}

function Wallet() {
  const [data, setData] = useState<any>(null)
  const [amt, setAmt] = useState(10000)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string|null>(null)
  const load = async () => {
    try { setData(await api.wallet()) } catch (e:any) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])
  const topup = async () => {
    setLoading(true); setErr(null)
    try { await api.topup(amt, `web-topup-${Date.now()}`); await load() } catch (e:any) { setErr(e.message) } finally { setLoading(false) }
  }
  return (
    <div className="max-w-4xl mx-auto mt-6 grid gap-6">
      <div className="card">
        <h2 className="text-lg font-semibold">Wallet</h2>
        {data ? (
          <div className="mt-2">
            <div>Phone: <b>{data.user.phone}</b></div>
            <div>Balance: <b>{data.wallet.balance_cents}</b> {data.wallet.currency_code}</div>
          </div>
        ) : <div>Loading...</div>}
      </div>
      <div className="card">
        <h3 className="font-semibold mb-2">Topup (Dev)</h3>
        <div className="flex gap-2 items-center">
          <input type="number" className="input w-48" value={amt} onChange={e=>setAmt(Number(e.target.value))} />
          <button className="btn" onClick={topup} disabled={loading}>Topup</button>
        </div>
        {err && <p className="text-red-600 mt-2 text-sm">{err}</p>}
      </div>
    </div>
  )
}

function Transfer() {
  const [to, setTo] = useState('')
  const [amt, setAmt] = useState(1000)
  const [ok, setOk] = useState<string| null>(null)
  const [err, setErr] = useState<string| null>(null)
  const submit = async () => {
    setOk(null); setErr(null)
    try { await api.transfer(to, amt, `web-transfer-${Date.now()}`); setOk('Transfer completed') } catch (e:any) { setErr(e.message) }
  }
  return (
    <div className="max-w-md mx-auto mt-6 card">
      <h2 className="text-lg font-semibold mb-2">P2P Transfer</h2>
      <label className="block text-sm mb-1">To phone</label>
      <input className="input mb-2" placeholder="+9639..." value={to} onChange={e=>setTo(e.target.value)} />
      <label className="block text-sm mb-1">Amount (cents)</label>
      <input className="input mb-3" type="number" value={amt} onChange={e=>setAmt(Number(e.target.value))} />
      <button className="btn w-full" onClick={submit}>Send</button>
      {ok && <p className="text-green-700 mt-2 text-sm">{ok}</p>}
      {err && <p className="text-red-600 mt-2 text-sm">{err}</p>}
    </div>
  )
}

function Merchant() {
  const [qr, setQr] = useState<{code:string, expires_at:string}|null>(null)
  const [amt, setAmt] = useState(5000)
  const [err, setErr] = useState<string|null>(null)
  const ensure = async () => {
    setErr(null)
    try {
      await api.kycApproveDev()
      await api.becomeMerchantDev()
    } catch (e:any) { setErr(e.message) }
  }
  const create = async () => {
    setErr(null)
    try { setQr(await api.createQR(amt)) } catch (e:any) { setErr(e.message) }
  }
  return (
    <div className="max-w-xl mx-auto mt-6 grid gap-6">
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Merchant Dev Setup</h2>
        <button className="btn" onClick={ensure}>Approve KYC + Become Merchant</button>
        {err && <p className="text-red-600 mt-2 text-sm">{err}</p>}
      </div>
      <div className="card">
        <h3 className="font-semibold mb-2">Create QR</h3>
        <div className="flex gap-2 items-center mb-3">
          <input className="input w-48" type="number" value={amt} onChange={e=>setAmt(Number(e.target.value))} />
          <button className="btn" onClick={create}>Create</button>
        </div>
        {qr && (
          <div className="grid gap-2">
            <div className="text-sm">Expires: {qr.expires_at}</div>
            <div className="flex items-center gap-4">
              <QRCode value={qr.code} size={140} />
              <div className="break-all text-sm">{qr.code}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const nav = useNavigate()
  useEffect(() => {
    if (!getToken()) nav('/login')
  }, [])
  return (
    <div>
      {getToken() && <Nav />}
      <div className="px-4">
        <Routes>
          <Route path="/" element={<Wallet />} />
          <Route path="/login" element={<Login />} />
          <Route path="/wallet" element={<Wallet />} />
          <Route path="/transfer" element={<Transfer />} />
          <Route path="/merchant" element={<Merchant />} />
          <Route path="/links" element={<LinksPage />} />
          <Route path="/subs" element={<SubscriptionsPage />} />
          <Route path="/statement" element={<StatementPage />} />
          <Route path="/qrpay" element={<QRPayPage />} />
          <Route path="/webhooks" element={<WebhooksPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </div>
    </div>
  )
}
