import AlphaLegalPage from "@/components/legal/AlphaLegalPage";
import { supportEmail } from "@/lib/support-email";

export default function TermsPage() {
  return <AlphaLegalPage kind="terms" supportEmail={supportEmail} />;
}
