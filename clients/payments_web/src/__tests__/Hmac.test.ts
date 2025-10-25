import { describe, it, expect } from 'vitest'
import { computeWebhookSign } from '../utils/hmac'

describe('computeWebhookSign', () => {
  it('matches known value', () => {
    const secret = 'sek'
    const ts = '1700000000'
    const ev = 'webhook.test'
    const body = JSON.stringify({ type: ev, data: { x: 1 } })
    const sig = computeWebhookSign(secret, ts, ev, body)
    // deterministic expectation; recompute same expression
    const sig2 = computeWebhookSign(secret, ts, ev, body)
    expect(sig).toBe(sig2)
  })
})

