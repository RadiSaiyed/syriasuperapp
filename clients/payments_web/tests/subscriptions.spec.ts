import { test, expect } from '@playwright/test'

test('create and dev-charge subscription', async ({ browser }) => {
  // Merchant login
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
  await mp.getByText('Wallet').click()
  const phoneText = await mp.getByText(/Phone:/).textContent()
  const merchantPhone = phoneText!.replace('Phone: ', '').trim()

  // Payer login
  const pctx = await browser.newContext()
  const pp = await pctx.newPage()
  await pp.goto('/')
  const pphone = `+9639${(Date.now()+1).toString().slice(-8)}`
  await pp.getByPlaceholder('+9639...').fill(pphone)
  await pp.getByText('Get OTP').click()
  await pp.getByPlaceholder('Your name').fill('Payer')
  await pp.getByPlaceholder('123456').fill('123456')
  await pp.getByText('Login').click()
  await pp.getByText('KYC').isHidden().catch(()=>{})
  await pp.getByText('Wallet').click()
  // Topup payer so charge can succeed
  await pp.getByLabel('Topup (Dev)', { exact: false }).locator('xpath=..').getByRole('spinbutton').fill('5000')
  await pp.getByText('Topup', { exact: true }).click()
  await pp.getByText('Subs').click()
  await pp.getByPlaceholder('+9639...').fill(merchantPhone)
  await pp.getByLabel('Amount (cents)').fill('2000')
  await pp.getByLabel('Interval (days)').fill('1')
  await pp.getByText('Create').click()
  // Row should appear then dev charge should work
  await pp.getByText('Your Subscriptions').waitFor()
  // Press Dev charge on first row
  const row = pp.locator('table tbody tr').first()
  await row.getByText('Dev charge').click()
  await expect(pp.getByText(/charged/i)).toBeVisible({ timeout: 10000 })
})

