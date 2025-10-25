import { api } from '../api'
import jsQR from 'jsqr'
import { useEffect, useRef } from 'react'

export default function QRPayPage() {
  const [code, setCode] = useState('')
  const [amount, setAmount] = useState<number | ''>('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [scanUI, setScanUI] = useState(false)
  const [cams, setCams] = useState<MediaDeviceInfo[]>([])
  const [deviceId, setDeviceId] = useState<string | undefined>(undefined)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [scanning, setScanning] = useState(false)
  const scanTimer = useRef<number | null>(null)

  const refreshCams = async () => {
    try { const list = await navigator.mediaDevices.enumerateDevices(); setCams(list.filter(d => d.kind === 'videoinput')) } catch {}
  }

  const onUploadImage = async (file: File) => {
    setErr(null); setMsg('')
    try {
      const img = new Image(); const fr = new FileReader()
      fr.onload = () => { img.onload = () => {
        const canvas = document.createElement('canvas'); canvas.width = img.width; canvas.height = img.height
        const ctx = canvas.getContext('2d')!; ctx.drawImage(img, 0, 0)
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
        const codeFound = jsQR(imageData.data as any, canvas.width, canvas.height)
        if (codeFound?.data) { setCode(codeFound.data); setMsg('QR decoded from image') } else { setErr('Could not decode QR from image') }
      }; img.src = fr.result as string }
      fr.readAsDataURL(file)
    } catch (e:any) { setErr(e.message) }
  }

  const stopScan = () => {
    setScanning(false)
    if (scanTimer.current) { window.clearInterval(scanTimer.current); scanTimer.current = null }
    const v = videoRef.current; const stream = v?.srcObject as MediaStream | null
    stream?.getTracks().forEach(t => t.stop()); if (v) v.srcObject = null
  }

  const startScan = async () => {
    setErr(null); setMsg('')
    try {
      const constraints: MediaStreamConstraints = { video: deviceId ? { deviceId: { exact: deviceId } } as any : { facingMode: 'environment' } }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      const v = videoRef.current!; v.srcObject = stream; await v.play(); setScanning(true)
      const c = canvasRef.current!; const ctx = c.getContext('2d')!
      scanTimer.current = window.setInterval(() => {
        if (!v.videoWidth || !v.videoHeight) return
        c.width = v.videoWidth; c.height = v.videoHeight
        ctx.drawImage(v, 0, 0, c.width, c.height)
        const id = ctx.getImageData(0,0,c.width,c.height)
        const found = jsQR(id.data as any, c.width, c.height)
        if (found?.data) { setCode(found.data); setMsg('QR detected'); stopScan() }
      }, 250)
    } catch (e:any) { setErr(e.message) }
  }

  useEffect(() => () => { stopScan() }, [])

  const submit = async () => {
    setErr(null); setMsg('')
    try { const idem = `web-qr-${Date.now()}`; const res = await api.payQR(code, idem, amount === '' ? undefined : Number(amount)); setMsg(`Paid: ${res.status}`) } catch (e:any) { setErr(e.message) }
  }

  return (
    <div className="max-w-xl mx-auto mt-6 card">
      <h2 className="text-lg font-semibold mb-2">Pay QR</h2>
      <div className="mb-3 flex gap-2 items-center">
        <button className="btn" onClick={async ()=>{ await refreshCams(); setScanUI(s=>!s); if (scanUI) stopScan() }}>{scanUI? 'Hide Scanner' : 'Scan with Camera'}</button>
        {cams.length>0 && (
          <select className="input w-64" value={deviceId || ''} onChange={e=>setDeviceId(e.target.value || undefined)}>
            <option value="">Default camera</option>
            {cams.map(c => <option key={c.deviceId} value={c.deviceId}>{c.label || `Camera ${c.deviceId.slice(0,6)}`}</option>)}
          </select>
        )}
        <label className="text-sm">
          <span className="btn">Upload Photo</span>
          <input type="file" accept="image/*" className="hidden" onChange={e=>{ const f=e.target.files?.[0]; if (f) onUploadImage(f) }} />
        </label>
      </div>
      {scanUI && (
        <div className="mb-3 grid gap-2">
          <video ref={videoRef} className="w-full rounded bg-black" muted playsInline />
          <canvas ref={canvasRef} className="hidden" />
          {!scanning ? <button className="btn" onClick={startScan}>Start Scan</button> : <button className="btn" onClick={stopScan}>Stop</button>}
        </div>
      )}
      <label className="block text-sm mb-1">QR Code string (PAY:v1;code=...)</label>
      <input className="input mb-2" placeholder="PAY:v1;code=..." value={code} onChange={e=>setCode(e.target.value)} />
      <label className="block text-sm mb-1">Amount (static QR requires amount)</label>
      <input className="input mb-3 w-48" type="number" value={amount} onChange={e=>setAmount(e.target.value===''? '': Number(e.target.value))} />
      <button className="btn" onClick={submit} disabled={!code}>Pay</button>
      {msg && <div className="text-green-700 text-sm mt-2">{msg}</div>}
      {err && <div className="text-red-600 text-sm mt-2">{err}</div>}
    </div>
  )
}
