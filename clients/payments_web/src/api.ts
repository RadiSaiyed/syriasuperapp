const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080'

async function http<T>(path: string, opts: RequestInit = {}, auth = false): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as any || {})
  }
  if (auth) {
    const tok = localStorage.getItem('token')
    if (tok) headers['Authorization'] = `Bearer ${tok}`
  }
  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
  if (!res.ok) {
    const txt = await res.text().catch(()=>'')
    throw new Error(`${res.status} ${res.statusText}: ${txt}`)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return await res.json() as T
  return (await res.text()) as unknown as T
}

export const api = {
  requestOtp: (phone: string) => http<{detail: string}>(`/auth/request_otp`, { method: 'POST', body: JSON.stringify({ phone }) }),
  verifyOtp: (phone: string, otp: string, name: string) => http<{access_token: string}>(`/auth/verify_otp`, { method: 'POST', body: JSON.stringify({ phone, otp, name }) }),
  wallet: () => http<{user:{phone:string,is_merchant:boolean}, wallet:{balance_cents:number,currency_code:string}}>(`/wallet`, {}, true),
  topup: (amount_cents: number, idempotency_key: string) => http(`/wallet/topup`, { method: 'POST', body: JSON.stringify({ amount_cents, idempotency_key }) }, true),
  transfer: (to_phone: string, amount_cents: number, idempotency_key: string) => http(`/wallet/transfer`, { method: 'POST', body: JSON.stringify({ to_phone, amount_cents, idempotency_key }) }, true),
  kycApproveDev: () => http(`/kyc/dev/approve`, { method: 'POST' }, true),
  becomeMerchantDev: () => http(`/payments/dev/become_merchant`, { method: 'POST' }, true),
  createQR: (amount_cents: number) => http<{code:string, expires_at:string}>(`/payments/merchant/qr`, { method: 'POST', body: JSON.stringify({ amount_cents }) }, true),
  payQR: (code: string, idempotency_key: string, amount_cents?: number) => http<{transfer_id:string,status:string}>(
    `/payments/merchant/pay`, { method: 'POST', body: JSON.stringify({ code, idempotency_key, amount_cents }) }, true
  ),
  // Links
  createLink: (amount_cents: number | null, expires_in_minutes?: number | null) => http<{code:string, expires_at?:string|null}>(
    `/payments/links`, { method: 'POST', body: JSON.stringify({ amount_cents, expires_in_minutes }) }, true
  ),
  payLink: (code: string, idempotency_key: string, amount_cents?: number) => http<{transfer_id:string,status:string}>(
    `/payments/links/pay`, { method: 'POST', body: JSON.stringify({ code, idempotency_key, amount_cents }) }, true
  ),
  // Subscriptions
  listSubscriptions: () => http<Array<{id:string, merchant_user_id:string, amount_cents:number, interval_days:number, status:string, next_charge_at:string}>>(`/subscriptions`, {}, true),
  createSubscription: (merchant_phone: string, amount_cents: number, interval_days: number) => http<{id:string,next_charge_at:string}>(
    `/subscriptions`, { method: 'POST', body: JSON.stringify({ merchant_phone, amount_cents, interval_days }) }, true
  ),
  cancelSubscription: (id: string) => http<{detail:string}>(`/subscriptions/${id}/cancel`, { method: 'POST' }, true),
  processDueDev: () => http<{processed:number,count:number}>(`/subscriptions/process_due`, { method: 'POST' }, true),
  forceDueDev: (id: string) => http<{detail:string}>(`/subscriptions/${id}/dev_force_due`, { method: 'POST' }, true),
  // Statement
  merchantStatementJson: (params?: {from?: string; to?: string}) => {
    const q = new URLSearchParams()
    if (params?.from) q.set('from_ts', params.from)
    if (params?.to) q.set('to_ts', params.to)
    const qs = q.toString();
    return http<{from:string,to:string,gross_cents:number,fees_cents:number,net_cents:number,rows:any[]}>(`/payments/merchant/statement${qs?`?${qs}`:''}`, {}, true)
  },
  merchantStatementCsv: (params?: {from?: string; to?: string}) => {
    const q = new URLSearchParams()
    if (params?.from) q.set('from_ts', params.from)
    if (params?.to) q.set('to_ts', params.to)
    q.set('format', 'csv')
    const qs = q.toString();
    return http<string>(`/payments/merchant/statement?${qs}`, {}, true)
  },
}
