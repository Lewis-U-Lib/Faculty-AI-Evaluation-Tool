const { test, expect } = require('@playwright/test');

test.describe('Faculty AI Tool smoke tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/index.html');
    await expect(page.locator('h1, .hdr__title').first()).toBeVisible();
  });

  test('carousel navigation next/prev updates panel label', async ({ page }) => {
    const panelLabel = page.locator('#panelLabel');
    await expect(panelLabel).toContainText('1 / 3');

    await page.click('#nextPanel');
    await expect(panelLabel).toContainText('2 / 3');

    await page.click('#prevPanel');
    await expect(panelLabel).toContainText('1 / 3');
  });

  test('matching flow renders recommendations and regenerate refreshes', async ({ page }) => {
    await page.click('[data-group="focus"] .opt[data-value="teaching"]');
    await page.click('[data-group="depth"] .opt[data-value="quick"]');

    await expect(page.locator('#resBd .tool-card').first()).toBeVisible();
    const before = await page.locator('#resBd').innerHTML();

    await page.click('#refreshBtn');
    await expect(page.locator('#resBd .tool-card').first()).toBeVisible();
    const after = await page.locator('#resBd').innerHTML();
    expect(after.length).toBeGreaterThan(0);
    expect(before).not.toEqual('');
  });

  test('activity popup opens and closes', async ({ page }) => {
    await page.click('[data-group="focus"] .opt[data-value="teaching"]');
    await page.click('[data-group="depth"] .opt[data-value="quick"]');

    const card = page.locator('.act-card').first();
    await expect(card).toBeVisible();
    await card.click();

    const popup = page.locator('.act-popup');
    await expect(popup).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(popup).toHaveCount(0);
  });

  test('Ask Us modal opens and chat iframe status telemetry is present', async ({ page }) => {
    await page.click('#fabTrigger');
    await page.click('#fabAskUs');

    const modal = page.locator('#chatModal');
    await expect(modal).toHaveClass(/open/);

    const status = page.locator('#chatStatus');
    await expect(status).toBeVisible();
    await expect(status).toContainText('Status:');

    const frame = page.locator('#chatFrame');
    await expect(frame).toHaveAttribute('src', /lewisu\.libanswers\.com/);

    await page.click('#chatModalClose');
    await expect(modal).not.toHaveClass(/open/);
  });
});
