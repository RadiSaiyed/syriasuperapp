import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import QRPayPage from '../pages/QRPay'

const fetchMock = vi.fn()
global.fetch = fetchMock as any

describe('QR Pay page', () => {
  beforeEach(() => fetchMock.mockReset())
  it('pays a dynamic QR', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.toString().includes('/payments/merchant/pay')) return Promise.resolve(new Response(JSON.stringify({transfer_id:'t', status:'completed'}), {status:200, headers:{'Content-Type':'application/json'}}))
      return Promise.resolve(new Response('', {status:404}))
    })
    render(<QRPayPage />)
    fireEvent.change(screen.getByPlaceholderText('PAY:v1;code=...'), {target:{value:'PAY:v1;code=abc'}})
    fireEvent.click(screen.getByText('Pay'))
    await screen.findByText(/Paid: completed/)
  })
})

