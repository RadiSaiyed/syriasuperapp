import { test, expect } from '@playwright/test'

test('login and see wallet', async ({ page }) => {
  // Assumes backend at VITE_API_BASE (default http://localhost:8080) with dev OTP
  const phone = `+9639${Date.now().toString().slice(-8)}`
  await page.goto('/')
  await page.getByPlaceholder('+9639...').fill(phone)
  await page.getByText('Get OTP').click()
  await page.getByPlaceholder('Your name').fill('Web CI')
  await page.getByPlaceholder('123456').fill('123456')
  await page.getByText('Login').click()
  await expect(page.getByText('Wallet')).toBeVisible({ timeout: 10000 })
  await expect(page.getByText('Balance:')).toBeVisible()
})

