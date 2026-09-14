import AlphaLegalPage from "@/components/legal/AlphaLegalPage";
import { supportEmail } from "@/lib/support-email";

export default function PrivacyPage() {
  return <AlphaLegalPage kind="privacy" supportEmail={supportEmail} />;
}
