import { ImageResponse } from "next/og";
import { evidenceReceiptSharingEnabled } from "@/lib/private-alpha-flags";
import { receiptCopy } from "@/lib/receipt-copy";
import {
  readPublicReceipt,
  headlineReceiptMetric,
  type PublicReceiptPayload,
} from "@/lib/public-receipt-contract";

/**
 * The preview card, rendered server-side from the frozen snapshot.
 *
 * Why rendered rather than static: a static brand tile would say nothing about
 * the receipt, and an unlabelled card pasted into a thread reads as spam, which
 * kills the distribution loop the card exists to serve. A rendered card also
 * lets the provenance mark be guaranteed by code instead of remembered by
 * whoever drew the asset once.
 *
 * The image is a public artifact and inherits section 3 in full. Its inputs are
 * a named, hard-coded subset of an already sanitized payload, listed in
 * PREVIEW_FIELDS below. It reads no artifact, no run and no conversation, and it
 * makes no provider call: everything on the card is frozen data.
 */
export const dynamic = "force-dynamic";
export const revalidate = 0;
export const runtime = "nodejs";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tested with Argus";

// The whole of what may appear on the card. Adding to this list is a deliberate
// change to what Argus publishes, and it is asserted by test.
export const PREVIEW_FIELDS = [
  "idea_title",
  "symbols",
  "date_range.display",
  "headline_metric.label",
  "headline_metric.value",
] as const;

// The card is a public artifact too: never indexed, and never cached by Argus so
// a revoked receipt stops serving its old card on the next request. Platforms
// that already cached it are the honest limit stated in the product.
const IMAGE_HEADERS = {
  "X-Robots-Tag": "noindex, nofollow, noimageindex",
  "Cache-Control": "no-store, max-age=0",
};

const BACKGROUND = "#191c1f";
const FOREGROUND = "#ffffff";
const MUTED = "rgba(255,255,255,0.52)";
const ACCENT = "#5ba897";

// The card follows the receipt's own language, not a viewer's. There is no viewer
// when a crawler fetches it, and the frozen facts on the card are in that language
// already, so anything else produces a mixed-language public artifact.
function cardCopy(language: "en" | "es-419") {
  const copy = receiptCopy(language);
  return {
    framing: copy.framing.short,
    provenance: copy.provenance,
    gone: copy.tombstone.title,
  };
}

function previewFacts(payload: PublicReceiptPayload) {
  const headline = headlineReceiptMetric(payload);
  return {
    title: payload.idea_title,
    symbols: payload.symbols.join(", "),
    dates: payload.date_range.display,
    metricLabel: headline?.label ?? "",
    metricValue: headline?.value ?? "",
  };
}

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        background: BACKGROUND,
        padding: "68px 72px",
        fontFamily: "sans-serif",
      }}
    >
      {children}
    </div>
  );
}

function ProvenanceRow({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
      <div
        style={{
          width: 16,
          height: 16,
          borderRadius: 999,
          background: ACCENT,
        }}
      />
      <div
        style={{
          fontSize: 24,
          letterSpacing: 2,
          textTransform: "uppercase",
          color: MUTED,
        }}
      >
        {label}
      </div>
    </div>
  );
}

export default async function Image({
  params,
}: {
  params: Promise<{ receiptId: string }>;
}) {
  if (!evidenceReceiptSharingEnabled) {
    return new Response(null, { status: 404 });
  }
  const { receiptId } = await params;
  const result = await readPublicReceipt(receiptId);

  // A transient failure must not become a permanent-looking card. Platforms cache
  // preview images, so rendering "this one is gone" during an outage would leave a
  // revoked-looking card pinned to a receipt that is perfectly alive, and Argus
  // cannot clear a cache it does not own. No body and a retryable status means the
  // platform shows no card and asks again later, which is recoverable.
  if (result.kind === "unavailable") {
    return new Response(null, {
      status: 503,
      headers: { ...IMAGE_HEADERS, "Retry-After": "120" },
    });
  }

  if (result.kind === "revoked") {
    // No payload means no content language to follow, so the tombstone card falls
    // back to English.
    const copy = cardCopy("en");
    return new ImageResponse(
      (
        <Frame>
          <ProvenanceRow label={copy.provenance} />
          <div style={{ display: "flex", fontSize: 52, color: FOREGROUND }}>
            {copy.gone}
          </div>
          <div style={{ display: "flex", fontSize: 26, color: MUTED }}>
            {copy.framing}
          </div>
        </Frame>
      ),
      { ...size, headers: IMAGE_HEADERS },
    );
  }

  const copy = cardCopy(result.payload.content_language);
  const facts = previewFacts(result.payload);
  return new ImageResponse(
    (
      <Frame>
        <ProvenanceRow label={copy.provenance} />
        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <div
            style={{
              display: "flex",
              fontSize: 60,
              lineHeight: 1.1,
              fontWeight: 600,
              color: FOREGROUND,
            }}
          >
            {facts.title}
          </div>
          <div style={{ display: "flex", gap: 28, alignItems: "flex-end" }}>
            {facts.metricValue ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ display: "flex", fontSize: 24, color: MUTED }}>
                  {facts.metricLabel}
                </div>
                <div
                  style={{
                    display: "flex",
                    fontSize: 68,
                    fontWeight: 600,
                    color: ACCENT,
                  }}
                >
                  {facts.metricValue}
                </div>
              </div>
            ) : null}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", fontSize: 28, color: FOREGROUND }}>
            {[facts.symbols, facts.dates].filter(Boolean).join("  ·  ")}
          </div>
          <div style={{ display: "flex", fontSize: 24, color: MUTED }}>
            {copy.framing}
          </div>
        </div>
      </Frame>
    ),
    { ...size, headers: IMAGE_HEADERS },
  );
}
