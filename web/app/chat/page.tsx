import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import ChatInterface from "@/components/chat/ChatInterface";
import { DevModeBadge } from "@/components/ui/DevModeBadge";
import { guestAccessEnabled } from "@/lib/private-alpha-flags";
import { guestCaptchaConfigured } from "@/lib/guest-session";
import { resolveChatEntrySurface } from "@/lib/landing-entry";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function ChatPage() {
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
  if (!isMockAuth) {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.getUser();
    if (
      resolveChatEntrySurface({
        hasEstablishedUser: !error && Boolean(data.user),
        guestAccessEnabled,
        guestCaptchaConfigured,
      }) === "auth"
    ) {
      redirect("/?auth=login");
    }
  }

  return (
    <main className="min-h-[100dvh] bg-background text-foreground selection:bg-black/10 dark:selection:bg-white/20">
      <DevModeBadge />
      <ChatInterface />
    </main>
  );
}
