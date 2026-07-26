import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import ChatInterface from "@/components/chat/ChatInterface";
import { DevModeBadge } from "@/components/ui/DevModeBadge";

export default async function ChatPage() {
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";

  if (!isMockAuth) {
    const supabase = await createClient();
    const { data } = await supabase.auth.getSession();
    if (!data.session) {
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
