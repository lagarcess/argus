import { redirect } from "next/navigation";
import { supabase } from "@/lib/supabase-client";
import ChatInterface from "@/components/chat/ChatInterface";

export default async function ChatPage() {
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";

  if (!isMockAuth) {
    const { data } = await supabase.auth.getSession();
    if (!data.session) {
      redirect("/login");
    }
  }

  return (
    <main className="min-h-[100dvh] bg-background text-foreground selection:bg-black/10 dark:selection:bg-white/20">
      <ChatInterface />
    </main>
  );
}
