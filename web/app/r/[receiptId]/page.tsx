import type { Metadata } from "next";
import { headers } from "next/headers";
import ReceiptBody from "@/components/receipt/ReceiptBody";
import ReceiptNotice from "@/components/receipt/ReceiptNotice";
import { evidenceReceiptSharingEnabled } from "@/lib/private-alpha-flags";
import {
  readPublicReceipt,
  headlineReceiptMetric,
  type PublicReceiptResult,
} from "@/lib/public-receipt-contract";
import {
  formatReceiptDateRange,
  receiptCopy,
  receiptLanguageFromAcceptLanguage,
} from "@/lib/receipt-copy";
import { notFound } from "next/navigation";

// Revocation has to take effect on the next request, so nothing here is cached
// and nothing is prerendered.
export const dynamic = "force-dynamic";
export const revalidate = 0;

// Permanent, and there is no product surface that can change it. Repeated on the
// page as well as the layout so neither file can quietly drop it.
const RECEIPT_ROBOTS: Metadata["robots"] = {
  index: false,
  follow: false,
  nocache: true,
  googleBot: { index: false, follow: false, noimageindex: true },
};

type ReceiptPageProps = {
  params: Promise<{ receiptId: string }>;
};

// Needed so the preview image resolves to an absolute url in the card markup.
function metadataBase(): URL | undefined {
  const origin = process.env.ARGUS_APP_ORIGIN?.trim();
  if (!origin) return undefined;
  try {
    return new URL(origin);
  } catch {
    return undefined;
  }
}

async function resolveLanguage() {
  const requestHeaders = await headers();
  return receiptLanguageFromAcceptLanguage(
    requestHeaders.get("accept-language"),
  );
}

export async function generateMetadata({
  params,
}: ReceiptPageProps): Promise<Metadata> {
  if (!evidenceReceiptSharingEnabled) {
    return { title: "Argus", robots: RECEIPT_ROBOTS };
  }
  const { receiptId } = await params;
  const language = await resolveLanguage();
  const copy = receiptCopy(language);
  const result = await readPublicReceipt(receiptId);
  // Metadata is cached by the platforms that read it, so a transient failure gets
  // no claim at all rather than a permanent-sounding one. Titling an outage "this
  // one is gone" would pin that on a live receipt.
  if (result.kind === "unavailable") {
    return { title: "Argus", robots: RECEIPT_ROBOTS };
  }
  if (result.kind === "revoked") {
    return {
      title: copy.tombstone.title,
      description: copy.tombstone.detail,
      robots: RECEIPT_ROBOTS,
      metadataBase: metadataBase(),
    };
  }
  const headline = headlineReceiptMetric(result.payload);
  // Description is built from the frozen payload only, so the card shows the
  // same closed set of facts the page does and nothing more. Its labels and dates
  // come from the copy, not from the payload: a preview card is read by whoever the
  // link was sent to, in their language.
  const metricLabels = copy.metric_labels as Record<string, string>;
  const description = [
    result.payload.symbols.join(", "),
    formatReceiptDateRange(result.payload.date_range, copy, language),
    headline
      ? `${metricLabels[headline.key] ?? headline.key}: ${headline.value}`
      : null,
    copy.framing.short,
  ]
    .filter(Boolean)
    .join(" · ");
  return {
    title: `${result.payload.idea_title} · ${copy.provenance}`,
    description,
    robots: RECEIPT_ROBOTS,
    metadataBase: metadataBase(),
    openGraph: {
      type: "article",
      title: result.payload.idea_title,
      description,
      siteName: "Argus",
    },
    twitter: {
      card: "summary_large_image",
      title: result.payload.idea_title,
      description,
    },
  };
}

export default async function PublicReceiptPage({ params }: ReceiptPageProps) {
  if (!evidenceReceiptSharingEnabled) {
    notFound();
  }
  const { receiptId } = await params;
  const language = await resolveLanguage();
  const copy = receiptCopy(language);
  const result: PublicReceiptResult = await readPublicReceipt(receiptId);

  if (result.kind !== "available") {
    return (
      <div lang={language}>
        <ReceiptNotice kind={result.kind} copy={copy} />
      </div>
    );
  }

  return (
    <div lang={language}>
      <ReceiptBody
        payload={result.payload}
        createdAt={result.createdAt}
        copy={copy}
        language={language}
      />
    </div>
  );
}
