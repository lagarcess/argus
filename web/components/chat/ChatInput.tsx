import { useState } from "react";
import { ArrowUp } from "lucide-react";
import { useTranslation } from "react-i18next";

type ChatInputProps = {
  onSend: (text: string) => void;
};

export default function ChatInput({ onSend }: ChatInputProps) {
  const { t } = useTranslation();
  const [text, setText] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (text.trim()) {
      onSend(text);
      setText("");
    }
  };

  return (
    <form 
      onSubmit={handleSubmit}
      className="relative flex items-end w-full bg-white dark:bg-[#1f2227] rounded-[32px] border border-black/5 dark:border-white/5 shadow-lg shadow-black/5 dark:shadow-none focus-within:ring-2 focus-within:ring-black/20 dark:focus-within:ring-white/20 transition-all"
    >
      {/* Auto-growing Textarea logic would go here, using an input for simplicity of MVP */}
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t('chat.input_placeholder')}
        className="flex-1 bg-transparent border-none outline-none py-4 pl-6 text-[16px] text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500 font-medium tracking-tight h-14"
      />

      {/* Send Button */}
      <div className="p-2 shrink-0">
        <button 
          type="submit"
          disabled={!text.trim()}
          className="p-2.5 rounded-full bg-black text-white dark:bg-white dark:text-black disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-85 transition-opacity"
        >
          <ArrowUp className="w-5 h-5 stroke-[2.5]" />
        </button>
      </div>
    </form>
  );
}
