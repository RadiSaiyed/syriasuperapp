import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'

const fetchMock = vi.fn()
global.fetch = fetchMock as any

describe('Wallet page', () => {
  beforeEach(() => {
    localStorage.setItem('token','t')
    fetchMock.mockReset()
  })
  it('loads wallet info', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.toString().includes('/wallet')) return Promise.resolve(new Response(JSON.stringify({user:{phone:'+1',is_merchant:false}, wallet:{balance_cents:123,currency_code:'SYP'}}), {status:200, headers:{'Content-Type':'application/json'}}))
      return Promise.resolve(new Response('', {status:404}))
    })
    render(<MemoryRouter initialEntries={["/wallet"]}><App /></MemoryRouter>)
    await screen.findByText(/Balance:/)
    expect(screen.getByText(/123/)).toBeTruthy()
  })
})

