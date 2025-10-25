import { test, expect } from '@playwright/test'

test('merchant creates link and payer pays', async ({ browser }) => {
  const merchant = await browser.newContext()
  const mp = await merchant.newPage()
  await mp.goto('/')
  const mphone = `+9639${Date.now().toString().slice(-8)}`
  await mp.getByPlaceholder('+9639...').fill(mphone)
  await mp.getByText('Get OTP').click()
  await mp.getByPlaceholder('Your name').fill('Merchant')
  await mp.getByPlaceholder('123456').fill('123456')
  await mp.getByText('Login').click()
  await mp.getByText('Merchant').click()
  await mp.getByText('Approve KYC + Become Merchant').click()
  await mp.getByText('Links').click()
  await mp.getByLabel('Amount', { exact: false }).fill('1500')
  await mp.getByText('Create').click()
  const codeField = await mp.getByText('Link created').locator('xpath=..').locator('input,div').last()
  const codeText = await mp.getByText(/LINK:v1;code=/).textContent()
  expect(codeText).toBeTruthy()

  // Payer
  const payer = await browser.newContext()
  const pp = await payer.newPage()
  await pp.goto('/')
  const pphone = `+9639${(Date.now()+1).toString().slice(-8)}`
  await pp.getByPlaceholder('+9639...').fill(pphone)
  await pp.getByText('Get OTP').click()
  await pp.getByPlaceholder('Your name').fill('Payer')
  await pp.getByPlaceholder('123456').fill('123456')
  await pp.getByText('Login').click()
  await pp.getByText('Wallet').click()
  await pp.getByLabel('Topup (Dev)', { exact: false }).locator('xpath=..').getByRole('spinbutton').fill('5000')
  await pp.getByText('Topup', { exact: true }).click()
  await pp.getByText('Links').click()
  await pp.getByLabel('Code').fill(codeText!.replace('Code: ', ''))
  await pp.getByText('Pay').click()
  await expect(pp.getByText('Paid: completed')).toBeVisible()
})

