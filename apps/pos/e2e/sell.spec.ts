import { expect, test } from '@playwright/test'

/**
 * Drives the real app against a real backend. These cover the interactions that
 * unit tests cannot: the tap sequence itself, the long-press gesture, and whether
 * undo is visible before it is usable.
 *
 * Needs the stack running. See README, "Running the whole thing locally", and set
 * POS_DEVICE_TOKEN to a token from `make seed`.
 */
const TOKEN = process.env.POS_DEVICE_TOKEN

test.skip(!TOKEN, 'set POS_DEVICE_TOKEN to run the end-to-end tests')

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => indexedDB.deleteDatabase('festival-pos'))
  await page.goto('/')
  await page.fill('input', TOKEN as string)
  await page.click('button[type=submit]')
  await page.click('.picker button >> nth=0')
  await page.waitForSelector('.product')
})

test('a five-drink round is six taps', async ({ page }) => {
  for (let i = 0; i < 3; i++) await page.click('.product:has-text("Jupiler")')
  for (let i = 0; i < 2; i++) await page.click('.product:has-text("Water")')

  await expect(page.locator('[data-test=commit]')).toContainText('5')

  await page.click('[data-test=commit]')

  // The screen clears instantly for the next customer.
  await expect(page.locator('[data-test=commit]')).toContainText('0')
})

test('holding a product removes one', async ({ page }) => {
  const jupiler = page.locator('.product:has-text("Jupiler")')
  await jupiler.click()
  await jupiler.click()
  await expect(page.locator('[data-test=commit]')).toContainText('2')

  await jupiler.hover()
  await page.mouse.down()
  await page.waitForTimeout(600)
  await page.mouse.up()

  await expect(page.locator('[data-test=commit]')).toContainText('1')
})

test('undo is visible but disabled until something has been sold', async ({ page }) => {
  const undo = page.locator('[data-test=undo]')
  await expect(undo).toBeVisible()
  await expect(undo).toBeDisabled()

  await page.click('.product:has-text("Jupiler")')
  await page.click('[data-test=commit]')

  await expect(undo).toBeEnabled()
  await undo.click()
  await expect(undo).toBeDisabled()
})

test('tapping a chip in the order strip removes one', async ({ page }) => {
  await page.click('.product:has-text("Cola")')
  await page.click('.product:has-text("Cola")')
  await page.click('.strip .chip:has-text("Cola")')

  await expect(page.locator('[data-test=commit]')).toContainText('1')
})
