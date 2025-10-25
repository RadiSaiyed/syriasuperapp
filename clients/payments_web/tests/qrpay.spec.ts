import { test, expect } from '@playwright/test'

test('merchant creates QR and payer pays via QR', async ({ browser }) => {
  // Merchant
  const mctx = await browser.newContext()
  const mp = await mctx.newPage()
  await mp.goto('/')
  const mphone = `+9639${Date.now().toString().slice(-8)}`
  await mp.getByPlaceholder('+9639...').fill(mphone)
  await mp.getByText('Get OTP').click()
  await mp.getByPlaceholder('Your name').fill('Merchant')
  await mp.getByPlaceholder('123456').fill('123456')
  await mp.getByText('Login').click()
  await mp.getByText('Merchant').click()
  await mp.getByText('Approve KYC + Become Merchant').click()
  // Create QR
  await mp.getByText('Create QR').isVisible()
  await mp.getByText('Create').click()
  const codeEl = mp.getByText(/PAY:v1;code=/)
  const codeText = await codeEl.textContent()
  expect(codeText).toBeTruthy()

  // Payer
  const pctx = await browser.newContext()
  const pp = await pctx.newPage()
  await pp.goto('/')
  const pphone = `+9639${(Date.now()+1).toString().slice(-8)}`
  await pp.getByPlaceholder('+9639...').fill(pphone)
  await pp.getByText('Get OTP').click()
  await pp.getByPlaceholder('Your name').fill('Payer')
  await pp.getByPlaceholder('123456').fill('123456')
  await pp.getByText('Login').click()
  // Topup
  await pp.getByText('Wallet').click()
  await pp.getByText('Topup').click()
  // QR Pay
  await pp.getByText('QR Pay').click()
  await pp.getByPlaceholder('PAY:v1;code=...').fill(codeText!.replace('PAY Code: ', ''))
  await pp.getByText('Pay', { exact: true }).click()
  await expect(pp.getByText('Paid: completed')).toBeVisible()
})

