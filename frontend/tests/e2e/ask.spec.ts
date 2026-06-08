import { expect, test } from "@playwright/test";

// Smoke: the happy path renders an answer and a source, with the API mocked.
test("asks a question and shows the answer + source", async ({ page }) => {
  await page.route("**/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Enable versioning in the bucket properties.",
        chunks: [
          { source_doc: "s3/versioning.md", link: "https://example.com/v", cosine_distance: 0.1 },
        ],
        session: { id: "sess-1", used: 1, limit: 20 },
      }),
    });
  });

  await page.goto("/");
  await page.getByLabel(/your question/i).fill("How do I enable versioning?");
  await page.getByRole("button", { name: /ask/i }).click();

  await expect(page.getByText(/enable versioning in the bucket properties/i)).toBeVisible();
  await expect(page.getByRole("link", { name: "s3/versioning.md" })).toBeVisible();
});
