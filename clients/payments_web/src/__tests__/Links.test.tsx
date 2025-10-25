import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import LinksPage from '../pages/Links'

const fetchMock = vi.fn()
global.fetch = fetchMock as any

describe('Links page', () => {
  beforeEach(() => fetchMock.mockReset())
  it('creates a dynamic link and pays it', async () => {
    fetchMock.mockImplementation((url: string, opts: any) => {
      if (url.toString().includes('/payments/links') && opts?.method==='POST' && !url.toString().includes('/pay'))
        return Promise.resolve(new Response(JSON.stringify({code:'LINK:v1;code=abcd'}), {status:200, headers:{'Content-Type':'application/json'}}))
      if (url.toString().includes('/payments/links/pay'))
        return Promise.resolve(new Response(JSON.stringify({transfer_id:'t', status:'completed'}), {status:200, headers:{'Content-Type':'application/json'}}))
      return Promise.resolve(new Response('', {status:404}))
    })
    render(<LinksPage />)
    fireEvent.change(screen.getByLabelText(/Amount/), {target:{value:'1234'}})
    fireEvent.click(screen.getByText('Create'))
    await screen.findByText(/Link created/)
    const codeInput = screen.getByDisplayValue('LINK:v1;code=abcd')
    expect(codeInput).toBeTruthy()
    fireEvent.click(screen.getByText('Pay'))
    await screen.findByText(/Paid: completed/)
  })
})

