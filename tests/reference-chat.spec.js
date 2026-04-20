const { test, expect } = require('@playwright/test');

test('Reference Guide Ask Us opens in-page chat modal', async ({ page }) => {
  await page.goto('/Reference.html');

  await page.click('#fabTrigger');
  await page.click('#fabAskUs');

  const modal = page.locator('#chatModal');
  await expect(modal).toHaveClass(/open/);
  await expect(page.locator('#chatFrame')).toHaveAttribute('src', /lewisu\.libanswers\.com/);

  await page.click('#chatModalClose');
  await expect(modal).not.toHaveClass(/open/);
});
