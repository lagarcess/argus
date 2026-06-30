import AlphaLegalPage from "@/components/legal/AlphaLegalPage";

const SUPPORT_EMAIL =
  process.env.NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL ?? "support@argus.local";

export default function TermsPage() {
  return <AlphaLegalPage kind="terms" supportEmail={SUPPORT_EMAIL} />;
}
