import ChatInterface from "@/components/chat/ChatInterface";

export default function ChatPage() {
  return (
    <main className="min-h-[100dvh] bg-[#f5f5f5] dark:bg-[#191c1f] text-black dark:text-white selection:bg-black/10 dark:selection:bg-white/20">
      <ChatInterface />
    </main>
  );
}
