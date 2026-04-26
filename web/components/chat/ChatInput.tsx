import { useState, useEffect, useRef, useMemo } from "react";
import { ArrowUp } from "lucide-react";
import { useTranslation } from "react-i18next";

type ChatInputProps = {
  onSend: (text: string) => void;
};

export default function ChatInput({ onSend }: ChatInputProps) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [typedText, setTypedText] = useState("");
  const [animState, setAnimState] = useState<"idle" | "typing" | "waiting" | "exiting">("idle");
  const [currentPromptIndex, setCurrentPromptIndex] = useState(0);
  const [isMounted, setIsMounted] = useState(false);
  const activityTimerRef = useRef<NodeJS.Timeout | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const prompts = useMemo(() => {
    const p = t('chat.placeholder_prompts', { returnObjects: true });
    return Array.isArray(p) ? p : [];
  }, [t]);

  // Handle hydration
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Idle tracking
  useEffect(() => {
    if (!isMounted) return;
    
    if (text || isFocused) {
      setAnimState("idle");
      setTypedText("");
      if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
      return;
    }

    const startCycle = () => {
      if (prompts.length === 0) return;
      // Use a stable random pick on first cycle to avoid jumping
      setCurrentPromptIndex((prev) => (prev + 1) % prompts.length);
      setAnimState("typing");
    };

    if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
    activityTimerRef.current = setTimeout(startCycle, 2000);
    
    return () => {
      if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
    };
  }, [text, isFocused, prompts.length, isMounted]);

  // Animation loop
  useEffect(() => {
    if (!isMounted || animState === "idle") return;

    if (animState === "typing") {
      const prompt = prompts[currentPromptIndex];
      if (!prompt) return;
      
      let i = 0;
      const interval = setInterval(() => {
        setTypedText(prompt.slice(0, i + 1));
        i++;
        if (i >= prompt.length) {
          clearInterval(interval);
          setAnimState("waiting");
        }
      }, 40);
      return () => clearInterval(interval);
    }

    if (animState === "waiting") {
      const timer = setTimeout(() => setAnimState("exiting"), 3000);
      return () => clearTimeout(timer);
    }

    if (animState === "exiting") {
      const timer = setTimeout(() => {
        setTypedText("");
        setCurrentPromptIndex((prev) => (prev + 1) % prompts.length);
        setAnimState("typing");
      }, 400); // Match globals.css duration
      return () => clearTimeout(timer);
    }
  }, [animState, currentPromptIndex, prompts, isMounted]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (text.trim()) {
      onSend(text);
      setText("");
    }
  };

  const handleContainerClick = () => {
    inputRef.current?.focus();
  };

  return (
    <form 
      onSubmit={handleSubmit}
      onClick={handleContainerClick}
      className="relative flex items-end w-full bg-white dark:bg-[#1f2227] rounded-[32px] border border-black/5 dark:border-white/5 shadow-lg shadow-black/5 dark:shadow-none focus-within:ring-2 focus-within:ring-black/20 dark:focus-within:ring-white/20 transition-all cursor-text"
    >
      <div className="relative flex-1 flex items-center min-w-0">
        <input
          ref={inputRef}
          data-testid="chat-input"
          type="text"
          value={text}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onChange={(e) => setText(e.target.value)}
          placeholder={isMounted && animState === "idle" ? t('chat.input_placeholder') : ""}
          className="flex-1 bg-transparent border-none outline-none py-4 pl-6 text-[16px] text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500 font-medium tracking-tight h-14"
        />
        
        {isMounted && animState !== "idle" && !text && (
          <div 
            key={`${currentPromptIndex}-${animState === "exiting"}`}
            className={`absolute left-6 pointer-events-none text-[16px] font-medium tracking-tight text-gray-400 dark:text-gray-500 flex items-center whitespace-nowrap overflow-hidden ${
              animState === "exiting" ? "animate-argus-swoosh-up" : ""
            }`}
          >
            {typedText}
            {animState === "typing" && (
              <span className="ml-0.5 w-[2px] h-4 bg-black/30 dark:bg-white/30 animate-pulse" />
            )}
          </div>
        )}
      </div>

      {/* Send Button */}
      <div className="p-2 shrink-0">
        <button 
          type="submit"
          data-testid="chat-send"
          disabled={!text.trim()}
          className="p-2.5 rounded-full bg-black text-white dark:bg-white dark:text-black disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-85 transition-opacity"
        >
          <ArrowUp className="w-5 h-5 stroke-[2.5]" />
        </button>
      </div>
    </form>
  );
}
