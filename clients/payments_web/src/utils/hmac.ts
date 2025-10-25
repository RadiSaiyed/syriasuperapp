import HmacSHA256 from 'crypto-js/hmac-sha256'
import Hex from 'crypto-js/enc-hex'

// Compute webhook signature: HMAC_SHA256(secret, ts + event + body)
export function computeWebhookSign(secret: string, ts: string, event: string, body: string): string {
  const msg = (ts || '') + (event || '') + (body || '')
  const mac = HmacSHA256(msg, secret)
  return mac.toString(Hex)
}

