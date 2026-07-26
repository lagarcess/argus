import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import ChatInterface from "@/components/chat/ChatInterface";
import { DevModeBadge } from "@/components/ui/DevModeBadge";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function ChatPage() {
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
  const guestAccessEnabled =
    process.env.NEXT_PUBLIC_GUEST_ACCESS_ENABLED === "true";

  if (!isMockAuth) {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.getUser();
    if (error || !data.user) {
      if (guestAccessEnabled) {
        redirect("/");
      }
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
