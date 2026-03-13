import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('should redirect to login when unauthenticated', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);
  });

  test('should show registration link on login page', async ({ page }) => {
    await page.goto('/login');
    const registerLink = page.getByRole('link', { name: /register|注册/i });
    await expect(registerLink).toBeVisible();
  });
});
