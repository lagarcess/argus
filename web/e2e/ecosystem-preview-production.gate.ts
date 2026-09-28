import { expect, test } from "@playwright/test";

// Run only with the production config; the general suite serves development.

test("the ecosystem route is unavailable in a production build", async ({ request }) => {
  const response = await request.get("/dev/ecosystem");
  const body = await response.text();
  expect([200, 404]).toContain(response.status());
  // This route follows the existing server notFound() guard. Next may start
  // streaming the shell with HTTP 200 before the guard resolves; in that case
  // its explicit server not-found marker is required. This is not a claim of
  // an HTTP-level 404 guarantee (the proxy-guarded result playground has one).
  if (response.status() === 200) expect(body).toContain("NEXT_HTTP_ERROR_FALLBACK;404");
  expect(body).not.toContain('data-testid="ecosystem-preview"');
});

for (const route of ["/", "/chat", "/?auth=login", "/?auth=signup"]) {
  test(`the existing ${route} entry still renders without the preview`, async ({ request }) => {
    const response = await request.get(route);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("text/html");
    const body = await response.text();
    expect(body).not.toContain('data-testid="ecosystem-preview"');
    expect(body).not.toContain("NEXT_HTTP_ERROR_FALLBACK;404");
  });
}
