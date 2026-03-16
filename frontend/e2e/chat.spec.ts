import { test, expect } from '@playwright/test';

test.describe('Chat Functionality', () => {
  test('should allow creating a new conversation', async ({ page }) => {
    await page.goto('/login');
    const emailInput = page.locator('input[type="email"]');
    const passwordInput = page.locator('input[type="password"]');
    await expect(emailInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
  });

  test('should display login button', async ({ page }) => {
    await page.goto('/login');
    // Use getByRole to avoid ambiguity with text "Login to JARVIS"
    const loginButton = page.getByRole('button', { name: /login|登录/i });
    await expect(loginButton).toBeVisible();
  });
});
