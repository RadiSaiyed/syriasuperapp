import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'

const fetchMock = vi.fn()
global.fetch = fetchMock as any

describe('Login flow', () => {
  beforeEach(() => {
    localStorage.clear()
    fetchMock.mockReset()
  })
  it('requests OTP and verifies', async () => {
    fetchMock.mockImplementation((url: string, opts: any) => {
      if (url.toString().includes('/auth/request_otp')) return Promise.resolve(new Response(JSON.stringify({detail:'ok'}), {status:200, headers:{'Content-Type':'application/json'}}))
      if (url.toString().includes('/auth/verify_otp')) return Promise.resolve(new Response(JSON.stringify({access_token:'t'}), {status:200, headers:{'Content-Type':'application/json'}}))
      if (url.toString().includes('/wallet')) return Promise.resolve(new Response(JSON.stringify({user:{phone:'+1',is_merchant:false}, wallet:{balance_cents:0,currency_code:'SYP'}}), {status:200, headers:{'Content-Type':'application/json'}}))
      return Promise.resolve(new Response('', {status:404}))
    })
    render(<MemoryRouter initialEntries={["/login"]}><App /></MemoryRouter>)
    fireEvent.change(screen.getByPlaceholderText('+9639...'), {target:{value:'+9639000'}})
    fireEvent.click(screen.getByText('Get OTP'))
    await screen.findByText(/OTP/)
    fireEvent.change(screen.getByPlaceholderText('Your name'), {target:{value:'Web'}})
    fireEvent.change(screen.getByPlaceholderText('123456'), {target:{value:'123456'}})
    fireEvent.click(screen.getByText('Login'))
    await waitFor(() => expect(localStorage.getItem('token')).toBe('t'))
  })
})

