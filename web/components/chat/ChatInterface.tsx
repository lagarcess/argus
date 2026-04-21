"use client";

import { useState, useRef, useEffect, UIEvent } from "react";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import { Menu, Plus, ChevronDown, Trash2, Pin, Edit2, Briefcase, Search, Settings, X, ArrowLeft, ArrowDown, History, Folder, Archive, ChevronRight, FolderPlus, MessageSquarePlus, MessageSquare, LineChart } from "lucide-react";
import Link from "next/link";
import StrategiesView from "../views/StrategiesView";
import PortfoliosView from "../views/PortfoliosView";
import SettingsView from "../views/SettingsView";

type Message = {
  id: string;
  role: "user" | "ai";
  content: string;
};

const MOCK_CONVERSATION: Message[] = [
  { id: "1", role: "ai", content: "Welcome to Argus. I can help you simulate and backtest any portfolio strategy. What are we building today?" },
  { id: "2", role: "user", content: "I want to test a Moon Mission strategy on tech stocks from 2020 to 2024." },
  { id: "3", role: "ai", content: "A 'Moon Mission' (Momentum Breakout) strategy on Tech Stocks. Excellent choice.\n\nI'll configure this to buy heavily when a stock breaks its 50-day high and hold until momentum significantly shifts." },
  { id: "4", role: "user", content: "Let's stick to just AAPL, MSFT, and NVDA for this test." },
  { id: "5", role: "ai", content: "Understood. Filtering the asset class to pure large-cap tech: AAPL, MSFT, and NVDA.\n\nHistorically, applying a Moon Mission momentum strategy on these specifically during the 2020-2024 window generates extreme volatility but significant upside. Should we account for any trailing stop-losses, or ride out the drops?" },
  { id: "6", role: "user", content: "No stop losses. HODL through the dips, but take 20% profit if it jumps 50% in a month." },
  { id: "7", role: "ai", content: "Got it. Adding a strict 20% fractional take-profit condition triggered off a >50% 30-day velocity spike.\n\nRunning the simulation engine over the 4-year dataset now. Please wait a moment." },
  { id: "8", role: "ai", content: "Simulation complete.\n\nHere are the top-level results:\n- Total Strategy Return: +312%\n- Max Drawdown: -41.2% (Nov 2022)\n- Win Rate on Profit Taking: 84%\n\nYour most profitable asset was NVDA, triggering the 50% velocity take-profit rule exactly 4 times in 2023. \n\nWould you like me to generate the visual cards for these metrics?" },
  { id: "9", role: "user", content: "That looks insane. What if we applied the exact same rules to a BTFD strategy instead of Moon Mission?" },
  { id: "10", role: "ai", content: "Switching the engine to BTFD (Buy The F*cking Dip) / Mean Reversion.\n\nInstead of buying the breakouts, the algorithm will now accumulate massive positions whenever AAPL, MSFT, or NVDA drop more than 15% below their 50-day moving average.\n\nRunning the simulation... " },
  { id: "11", role: "ai", content: "BTFD Results (2020-2024):\n\n- Total Strategy Return: +185%\n- Max Drawdown: -22.1%\n\nNotice the difference? Because you are buying the dips instead of chasing the breakouts, your max drawdown is cut entirely in half (safer), but you miss out on the parabolic NVDA runs of late 2023 because the asset rarely dipped enough to trigger a buy event." }
];

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>(MOCK_CONVERSATION);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  const [activeContextMenu, setActiveContextMenu] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [isScrolledUp, setIsScrolledUp] = useState(false);
  const [isScrolling, setIsScrolling] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRecentsExpanded, setIsRecentsExpanded] = useState(true);
  const [currentView, setCurrentView] = useState<'chat' | 'strategies' | 'portfolios' | 'settings'>('chat');
  const [showHeaderMenu, setShowHeaderMenu] = useState(false);
  const [activeSubmenu, setActiveSubmenu] = useState<"none" | "history" | "portfolio">("none");

  useEffect(() => {
    if (!showHeaderMenu) {
      setActiveSubmenu("none");
    }
  }, [showHeaderMenu]);

  const handleScrollEvent = (e: React.UIEvent<HTMLDivElement>) => {
    setIsScrolling(true);
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }
    scrollTimeoutRef.current = setTimeout(() => {
      setIsScrolling(false);
    }, 800);

    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    const distanceToBottom = scrollHeight - Math.ceil(scrollTop) - clientHeight;
    setIsScrolledUp(distanceToBottom > 200);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSend = (text: string) => {
    if (!text.trim()) return;
    
    const newUserMsg: Message = { id: Date.now().toString(), role: "user", content: text };
    setMessages((prev) => [...prev, newUserMsg]);
    
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: "ai", content: "Let me crunch the numbers on that..." },
      ]);
    }, 600);
  };

  return (
    <div className="relative w-full h-[100dvh] bg-[#f9f9f9] dark:bg-[#141517] overflow-hidden flex">
      <div className="absolute inset-y-0 left-0 w-full md:w-[320px] h-full flex flex-col pt-12 pb-8 px-6 z-0">
        <div className="flex items-center justify-between w-full mb-10">
           <h1 className="text-[26px] font-medium tracking-tight text-black dark:text-white" style={{ fontFamily: 'var(--font-space-grotesk)' }}>argus</h1>
           <button 
             className="flex items-center justify-center p-2 rounded-xl border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-black dark:text-white" 
             onClick={() => { setIsSidebarOpen(false); setCurrentView('chat'); setMessages(MOCK_CONVERSATION); }}
             title="New chat"
           >
              <MessageSquarePlus className="w-5 h-5" />
           </button>
        </div>
        
        <div className="flex flex-col gap-3 mb-8">
           <button 
             className="flex items-center justify-center w-full py-3.5 rounded-[16px] border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-black dark:text-white text-[15px] font-medium shadow-[0_2px_10px_rgba(0,0,0,0.02)]"
             onClick={() => { setCurrentView('portfolios'); setIsSidebarOpen(false); }}
           >
             Portfolios
           </button>
           <button 
             className="flex items-center justify-center w-full py-3.5 rounded-[16px] border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-black dark:text-white text-[15px] font-medium shadow-[0_2px_10px_rgba(0,0,0,0.02)]"
             onClick={() => { setCurrentView('strategies'); setIsSidebarOpen(false); }}
           >
             Strategies
           </button>
        </div>

        <div className="flex flex-col flex-1 overflow-hidden">
           <button 
             onClick={() => setIsRecentsExpanded(!isRecentsExpanded)}
             className="flex items-center gap-1.5 group w-fit mb-3"
           >
             <h2 className="text-[20px] font-medium tracking-tight text-black dark:text-white" style={{ fontFamily: 'var(--font-space-grotesk)' }}>Recents</h2>
             <ChevronDown className={`w-4 h-4 text-black/40 dark:text-white/40 transition-transform duration-200 mt-1 ${isRecentsExpanded ? 'rotate-0' : '-rotate-90'}`} />
           </button>
           
           <div className={`flex flex-col gap-1 -mx-3 px-3 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${isRecentsExpanded ? 'max-h-[40vh] opacity-100' : 'max-h-0 opacity-0'}`}>
             <button className="flex flex-col items-start w-full py-3 px-4 rounded-[16px] hover:bg-black/5 dark:hover:bg-white/5 transition-colors shrink-0" onClick={() => setIsSidebarOpen(false)}>
               <span className="text-[15px] font-medium text-black dark:text-white truncate w-full text-left">Short BTC Volatility</span>
               <span className="text-[12px] text-black/40 dark:text-white/40 mt-0.5">today • Strategy</span>
             </button>

             <button className="flex flex-col items-start w-full py-3 px-4 rounded-[16px] hover:bg-black/5 dark:hover:bg-white/5 transition-colors shrink-0" onClick={() => setIsSidebarOpen(false)}>
               <span className="text-[15px] font-medium text-black dark:text-white truncate w-full text-left">Crypto Moon Mission</span>
               <span className="text-[12px] text-black/40 dark:text-white/40 mt-0.5">yesterday • Chat</span>
             </button>

             <button className="flex flex-col items-start w-full py-3 px-4 rounded-[16px] hover:bg-black/5 dark:hover:bg-white/5 transition-colors shrink-0" onClick={() => setIsSidebarOpen(false)}>
               <span className="text-[15px] font-medium text-black dark:text-white truncate w-full text-left">Tech Breakouts Q3</span>
               <span className="text-[12px] text-black/40 dark:text-white/40 mt-0.5">Oct 28, 2024 • Portfolio</span>
             </button>
           </div>
        </div>

        <div className="flex items-center gap-4 mt-auto pt-4">
           <button 
             onClick={() => { setCurrentView('settings'); setIsSidebarOpen(false); }}
             className="flex items-center justify-center w-12 h-12 rounded-full border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-black dark:text-white shrink-0 shadow-[0_2px_10px_rgba(0,0,0,0.02)]" title="Settings"
           >
             <Settings className="w-5 h-5" />
           </button>
           <div className="relative flex-1">
             <Search className="w-5 h-5 absolute left-5 top-1/2 -translate-y-1/2 text-black/40 dark:text-white/40 pointer-events-none" />
             <input 
               type="text" 
               placeholder="Search..." 
               value={searchText}
               onChange={(e) => setSearchText(e.target.value)}
               onBlur={() => setTimeout(() => setSearchText(""), 200)}
               className="w-full h-[52px] pl-[48px] pr-12 rounded-full border border-black/10 dark:border-white/10 bg-white/50 dark:bg-[#1f2225]/50 backdrop-blur-xl focus:bg-white dark:focus:bg-[#1f2225] focus:outline-none focus:ring-2 focus:ring-black/5 dark:focus:ring-white/5 transition-all text-[15px] shadow-lg text-black dark:text-white placeholder:text-black/40 dark:placeholder:text-white/40"
             />
             {searchText && (
               <button 
                 onClick={() => setSearchText("")} 
                 className="absolute right-4 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-full bg-black/10 dark:bg-white/10 text-black/60 dark:text-white/60 hover:bg-black/20 dark:hover:bg-white/20 transition-colors"
               >
                 <X className="w-3.5 h-3.5" />
               </button>
             )}
          </div>
        </div>
      </div>

      <div 
        className={`absolute inset-0 flex flex-col w-full h-full bg-[#f9f9f9] dark:bg-[#141517] overflow-hidden transform-gpu transition-all duration-[500ms] ease-[cubic-bezier(0.16,1,0.3,1)] z-10 ${
          isSidebarOpen ? 'translate-x-[75%] md:translate-x-[320px] scale-[0.93] rounded-[32px] md:rounded-[32px] shadow-[-20px_0_40px_rgba(0,0,0,0.08)] dark:shadow-[-20px_0_40px_rgba(0,0,0,0.5)] cursor-pointer' : 'translate-x-0 scale-100 rounded-none'
        }`}
        onClick={() => {
          if (isSidebarOpen) setIsSidebarOpen(false);
        }}
      >
      {currentView === 'chat' && (
        <div className="flex flex-col w-full h-[100dvh] max-w-3xl mx-auto relative overflow-hidden" style={{ pointerEvents: isSidebarOpen ? 'none' : 'auto' }}>
      
      <div className="absolute top-0 inset-x-0 h-28 z-10 pointer-events-none backdrop-blur-[8px] bg-[#f5f5f5]/10 dark:bg-[#191c1f]/20 [mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)]" />

      <div className="absolute top-4 left-4 z-20">
        <button 
          onClick={() => setIsSidebarOpen(!isSidebarOpen)} 
          className="flex items-center justify-center p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-black dark:text-white"
          title="Open Menu"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      <div className="absolute top-6 inset-x-0 w-full flex justify-center z-20 pointer-events-none">
        <h1 className="text-[16px] font-medium tracking-tight pointer-events-auto">argus</h1>
      </div>

      <div className="absolute top-4 right-4 z-30">
        <button 
          onClick={() => setShowHeaderMenu(!showHeaderMenu)}
          className="flex items-center justify-center p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-black dark:text-white"
          title="Chat Options"
        >
          <History className="w-5 h-5" />
        </button>

        {showHeaderMenu && (
          <>
            <div 
              className="fixed inset-0 bg-black/20 dark:bg-black/80 md:bg-transparent z-40 animate-in fade-in duration-300 md:duration-0"
              onClick={() => setShowHeaderMenu(false)}
            />

            <div className="fixed md:absolute bottom-0 md:bottom-auto md:top-full inset-x-0 md:right-0 md:left-auto md:mt-1 w-full md:w-[240px] z-50 perspective-[1000px]">
                
                <div 
                  className={`w-full bg-white dark:bg-[#1f2225] rounded-t-[32px] md:rounded-[24px] rounded-b-none md:rounded-b-[24px] shadow-[0_-8px_30px_rgba(0,0,0,0.12)] md:shadow-xl dark:shadow-black/50 border-t md:border border-black/5 dark:border-white/5 pb-10 md:pb-2 pt-2 transform-gpu origin-bottom md:origin-top transition-all duration-400 ease-[cubic-bezier(0.16,1,0.3,1)] ${
                    activeSubmenu !== 'none' ? 'scale-[0.93] opacity-40 blur-[1px] pointer-events-none' : 'scale-100 opacity-100 blur-0'
                  } animate-in slide-in-from-bottom-[100%] md:slide-in-from-top-2 fade-in duration-300`}
                >
                  <div className="w-12 h-1.5 bg-black/10 dark:bg-white/10 rounded-full mx-auto my-3 md:hidden shrink-0" />

                  <button 
                    className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium"
                    onClick={() => setShowHeaderMenu(false)}
                  >
                    <Plus className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                    New chat
                  </button>
                  
                  <button 
                    className="w-full flex items-center justify-between px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium group"
                    onClick={(e) => { e.stopPropagation(); setActiveSubmenu('history'); }}
                  >
                    <div className="flex items-center gap-4">
                      <History className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                      View history
                    </div>
                    <ChevronRight className={`w-5 h-5 md:w-4 md:h-4 text-black/40 dark:text-white/40 transition-transform duration-[400ms] ${activeSubmenu === 'history' ? 'rotate-90' : 'group-hover:translate-x-0.5'}`} />
                  </button>
                  
                  <button 
                    className="w-full flex items-center justify-between px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium group"
                    onClick={(e) => { e.stopPropagation(); setActiveSubmenu('portfolio'); }}
                  >
                    <div className="flex items-center gap-4">
                      <Folder className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                      Add to portfolio
                    </div>
                    <ChevronRight className={`w-5 h-5 md:w-4 md:h-4 text-black/40 dark:text-white/40 transition-transform duration-[400ms] ${activeSubmenu === 'portfolio' ? 'rotate-90' : 'group-hover:translate-x-0.5'}`} />
                  </button>
                  
                  <button 
                    className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium"
                    onClick={() => setShowHeaderMenu(false)}
                  >
                    <Archive className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                    Archive
                  </button>
                  
                  <div className="h-px w-full bg-black/5 dark:bg-white/5 my-2 md:my-1" />
                  
                  <button 
                    className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-red-500/10 transition-colors text-left text-red-500 text-[16px] md:text-[15px] font-medium"
                    onClick={() => { setMessages([]); setShowHeaderMenu(false); }}
                  >
                    <Trash2 className="w-[18px] h-[18px] md:w-4 md:h-4 text-red-500" />
                    Delete chat
                  </button>
                </div>

              {/* Overlay Submenu Card Container */}
              {activeSubmenu !== 'none' && (
                <div 
                  className="absolute top-0 right-0 w-full min-h-full bg-white/95 dark:bg-[#1f2225]/95 backdrop-blur-[20px] rounded-t-[32px] md:rounded-[24px] rounded-b-none md:rounded-b-[24px] shadow-2xl dark:shadow-black/80 border-t md:border border-black/5 dark:border-white/5 py-2 z-10 animate-in fade-in slide-in-from-bottom-8 md:slide-in-from-top-6 duration-[400ms] ease-[cubic-bezier(0.16,1,0.3,1)] flex flex-col pb-8 md:pb-2"
                >
                  {/* Mobile Swap Handle */}
                  <div className="w-12 h-1.5 bg-black/10 dark:bg-white/10 rounded-full mx-auto my-3 md:hidden shrink-0" />

                  {/* Action Header back button */}
                  <button 
                    onClick={(e) => { e.stopPropagation(); setActiveSubmenu('none'); }} 
                    className="w-full flex items-center justify-between px-6 md:px-4 py-3 md:py-2 opacity-60 hover:opacity-100 transition-opacity mt-1 md:mt-0"
                  >
                    <span className="text-[14px] md:text-[13px] font-medium text-black dark:text-white tracking-wide uppercase">
                      {activeSubmenu === 'history' ? 'Past Sessions' : 'Portfolios'}
                    </span>
                    <ChevronRight className="w-5 h-5 md:w-4 md:h-4 text-black dark:text-white -rotate-90" />
                  </button>
                  
                  <div className="h-px w-[85%] mx-auto bg-black/5 dark:bg-white/5 mb-3 md:mb-2 mt-1" />

                  {/* Portfolio Options */}
                  {activeSubmenu === 'portfolio' && (
                    <div className="flex flex-col animate-in fade-in zoom-in-95 duration-200 delay-100 fill-mode-both">
                      <button className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium" onClick={() => setShowHeaderMenu(false)}>
                        <FolderPlus className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                        New portfolio
                      </button>
                      <button className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium" onClick={() => setShowHeaderMenu(false)}>
                        <Folder className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                        Alpha Volatility '24
                      </button>
                      <button className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium" onClick={() => setShowHeaderMenu(false)}>
                        <Folder className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                        Tech Breakouts Q3
                      </button>
                    </div>
                  )}

                  {/* History Options */}
                  {activeSubmenu === 'history' && (
                    <div className="flex flex-col animate-in fade-in zoom-in-95 duration-200 delay-100 fill-mode-both">
                      <button className="w-full flex flex-col justify-center px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left cursor-pointer" onClick={() => setShowHeaderMenu(false)}>
                        <div className="flex justify-between items-center w-full">
                          <span className="text-black dark:text-white text-[16px] md:text-[15px] font-medium truncate pr-2">Short BTC Volatility</span>
                          <span className="text-[14px] md:text-[12px] text-black/40 dark:text-white/40 shrink-0">Today</span>
                        </div>
                        <span className="text-[14px] md:text-[13px] text-black/50 dark:text-white/50 truncate w-full mt-1 md:mt-0.5">Parameters: 50d SMA, Take Profit 10%...</span>
                      </button>
                      <div className="h-px w-[85%] mx-auto bg-black/5 dark:bg-white/5 my-1 md:my-0" />
                      <button className="w-full flex flex-col justify-center px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left cursor-pointer" onClick={() => setShowHeaderMenu(false)}>
                        <div className="flex justify-between items-center w-full">
                          <span className="text-black dark:text-white text-[16px] md:text-[15px] font-medium truncate pr-2">Crypto Moon Mission</span>
                          <span className="text-[14px] md:text-[12px] text-black/40 dark:text-white/40 shrink-0">Nov 12</span>
                        </div>
                        <span className="text-[14px] md:text-[13px] text-black/50 dark:text-white/50 truncate w-full mt-1 md:mt-0.5">Assets: AAPL, MSFT, NVDA. No stop l...</span>
                      </button>
                    </div>
                  )}
                </div>
              )}

            </div>
            </>
          )}
        {/* End of Menu Stack */}
      </div>

      {/* Messages Scroll Area */}
      <div 
        ref={scrollContainerRef}
        onScroll={handleScrollEvent}
        className={`flex-1 overflow-y-auto px-4 pt-[80px] pb-[120px] space-y-8 scroll-smooth transition-colors duration-300 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent ${isScrolling ? "[&::-webkit-scrollbar-thumb]:bg-black/20 dark:[&::-webkit-scrollbar-thumb]:bg-white/20" : "[&::-webkit-scrollbar-thumb]:bg-transparent dark:[&::-webkit-scrollbar-thumb]:bg-transparent"}`}
      >
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} className="h-1 text-transparent font-medium" />
      </div>

      {/* Floating Scroll to Bottom Button */}
      {isScrolledUp && (
        <button
          onClick={scrollToBottom}
          className="fixed md:absolute bottom-32 md:bottom-28 right-4 md:right-6 p-3 rounded-full bg-white dark:bg-[#2c2c2e] text-black dark:text-white shadow-xl dark:shadow-black/50 border border-black/5 dark:border-white/10 hover:scale-105 transition-transform z-50 animate-in fade-in zoom-in-95 duration-200"
          aria-label="Scroll to bottom"
        >
          <ArrowDown className="w-5 h-5" />
        </button>
      )}

      {/* Progressive Bottom Glass Blur Layer */}
      <div className="absolute bottom-0 inset-x-0 h-40 z-10 pointer-events-none backdrop-blur-[0.8px] bg-[#f5f5f5]/10 dark:bg-[#191c1f]/20 [mask-image:linear-gradient(to_top,black_50%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_top,black_50%,transparent_100%)]" />

      {/* Bottom Input Container */}
      <div className="absolute bottom-6 inset-x-0 w-full px-4 z-20 pointer-events-none">
        <div className="pointer-events-auto max-w-3xl mx-auto shadow-2xl shadow-black/5 dark:shadow-black/50 rounded-[9999px]">
          <ChatInput onSend={handleSend} />
        </div>
      </div>

        </div>
      )}

      {currentView === 'strategies' && (
        <div className="w-full h-[100dvh]" style={{ pointerEvents: isSidebarOpen ? 'none' : 'auto' }}>
          <StrategiesView onMenuClick={() => setIsSidebarOpen(!isSidebarOpen)} onSettingsClick={() => setCurrentView('settings')} />
        </div>
      )}

      {currentView === 'portfolios' && (
        <div className="w-full h-[100dvh]" style={{ pointerEvents: isSidebarOpen ? 'none' : 'auto' }}>
          <PortfoliosView onMenuClick={() => setIsSidebarOpen(!isSidebarOpen)} onSettingsClick={() => setCurrentView('settings')} />
        </div>
      )}

      {currentView === 'settings' && (
        <div className="w-full h-[100dvh]" style={{ pointerEvents: isSidebarOpen ? 'none' : 'auto' }}>
          <SettingsView onClose={() => setCurrentView('chat')} onLogout={() => window.location.href = '/'} />
        </div>
      )}

      </div>
    </div>
  );
}
