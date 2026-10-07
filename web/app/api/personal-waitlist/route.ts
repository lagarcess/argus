export function POST() {
  return Response.json(
    { error: "unavailable" },
    { status: 503, headers: { "Cache-Control": "no-store" } },
  );
}
