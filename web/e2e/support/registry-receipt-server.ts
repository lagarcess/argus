import { createServer } from "node:http";
import { registryReceiptFixture } from "./registry-receipt-fixture";

const views = new Map((["en", "es-419"] as const).map((language) => {
  const fixture = registryReceiptFixture(language);
  return [`/api/v1/public/receipts/${fixture.receipt.public_id}`, fixture.publicView];
}));
const server = createServer((request, response) => {
  const payload = request.method === "GET" ? views.get(request.url ?? "") : undefined;
  response.writeHead(payload ? 200 : 404, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  response.end(JSON.stringify(payload ?? { status: "unavailable" }));
});
server.listen(Number(process.env.REGISTRY_RECEIPT_API_PORT ?? 3191), "127.0.0.1");
for (const signal of ["SIGINT", "SIGTERM"] as const) process.on(signal, () => server.close(() => process.exit(0)));
