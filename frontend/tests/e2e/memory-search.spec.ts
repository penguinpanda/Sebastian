import { test, expect } from '@playwright/test';

test('memory search flow shows trace id', async ({ page }) => {
  await page.route('**/api/mcp/invoke', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        trace_id: 'trace-api-001',
        tool_name: 'search.answer',
        result: {
          summary: 'Found 1 relevant memory snippet(s) for your query.',
          evidence: ['我不吃花生'],
          retrieval_mode: 'hybrid',
          _audit: {
            trace_id: 'trace-api-001',
            user_id: 'user-001',
            action: 'invoke',
            tool_name: 'search.answer',
            timestamp: '2026-06-11T00:00:00Z',
          },
        },
        latency_ms: 8,
        status: 'ok',
        from_cache: false,
      }),
    });
  });

  await page.goto('/');
  await page.getByRole('button', { name: '确认' }).click();
  await page.getByRole('button', { name: '🧠 记忆检索' }).click();

  await page.getByPlaceholder('例：有什么饮食禁忌、我的身体状况、喜欢的烹饪方式').fill('饮食禁忌');
  await page.getByRole('button', { name: '搜索' }).click();

  await expect(page.getByText('trace-api-001')).toBeVisible();
  await expect(page.getByText('我不吃花生')).toBeVisible();
});
