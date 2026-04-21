"use client";

import { useState, useRef, useEffect } from "react";
import { Sparkles, ThumbsUp, ThumbsDown, MoreHorizontal, Copy, MessageSquareWarning } from "lucide-react";

type Message = {
  id: string;
  role: "user" | "ai";
  content: string;
};

export default function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const [showOptions, setShowOptions] = useState(false);
  const [menuPosition, setMenuPosition] = useState<"top" | "bottom">("bottom");
  const optionsRef = useRef<HTMLDivElement>(null);

  const toggleOptions = (e: React.MouseEvent) => {
    if (!showOptions) {
      const buttonRect = e.currentTarget.getBoundingClientRect();
      // If the button is too close to the bottom of the screen (e.g. within 160px), map the popup upwards
      if (buttonRect.bottom + 160 > window.innerHeight) {
        setMenuPosition("top");
      } else {
        setMenuPosition("bottom");
      }
      setShowOptions(true);
    } else {
      setShowOptions(false);
    }
  };

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (optionsRef.current && !optionsRef.current.contains(event.target as Node)) {
        setShowOptions(false);
      }
    }
    
    function handleScroll() {
      setShowOptions(false);
    }

    if (showOptions) {
      document.addEventListener("mousedown", handleClickOutside);
      // Use capture phase to ensure we catch the scroll event from the inner container natively
      window.addEventListener("scroll", handleScroll, true);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, [showOptions]);

  if (isUser) {
    return (
      <div className="flex w-full justify-end animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="max-w-[85%] bg-black/5 dark:bg-white/10 text-black dark:text-white px-5 py-3.5 rounded-[24px] rounded-br-sm text-[16px] leading-[1.5] tracking-[0.24px] font-normal shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full justify-start animate-in fade-in slide-in-from-bottom-2 duration-300 group">
      <div className="flex gap-4 max-w-[90%]">
        {/* Minimal AI Avatar/Icon */}
        <div className="w-8 h-8 shrink-0 rounded-full bg-[#191c1f] dark:bg-white flex items-center justify-center mt-1">
          <Sparkles className="w-4 h-4 text-white dark:text-[#191c1f]" />
        </div>
        
        {/* Elevated Raw Text & Actions */}
        <div className="flex flex-col mt-1.5">
          <div className="text-black dark:text-white text-[16px] leading-[1.6] tracking-[0.24px] whitespace-pre-wrap">
            {message.content}
          </div>
          
          {/* Feedback Icon Row (Tiny & Subtle) */}
          <div className="relative flex items-center gap-1.5 mt-2 opacity-50 hover:opacity-100 transition-opacity" ref={optionsRef}>
            <button className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors" title="Good response">
              <ThumbsUp className="w-3.5 h-3.5" />
            </button>
            <button className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors" title="Poor response">
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>
            <button 
              onClick={toggleOptions}
              className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors" 
              title="More Actions"
            >
              <MoreHorizontal className="w-3.5 h-3.5" />
            </button>

            {/* Popover Menu */}
            {showOptions && (
              <div className={`absolute ${menuPosition === "bottom" ? "top-full mt-2" : "bottom-full mb-2"} left-0 w-[220px] bg-white dark:bg-[#1f2225] rounded-[24px] shadow-xl dark:shadow-black/50 border border-black/5 dark:border-white/5 py-2 z-50 animate-in fade-in zoom-in-95 duration-200`}>
                <button 
                  className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                  onClick={() => { navigator.clipboard.writeText(message.content); setShowOptions(false); }}
                >
                  <Copy className="w-4 h-4 text-black/60 dark:text-white/60" />
                  Copy Plaintext
                </button>
                <button 
                  className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                  onClick={() => { navigator.clipboard.writeText(message.id); setShowOptions(false); }}
                >
                  <Copy className="w-4 h-4 text-black/60 dark:text-white/60" />
                  Copy ID
                </button>
                <button 
                  className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                  onClick={() => setShowOptions(false)}
                >
                  <MessageSquareWarning className="w-4 h-4 text-black/60 dark:text-white/60" />
                  Report Issue
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
