"use client";

import { useState, useRef, useEffect } from "react";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import { Menu, Plus, ChevronDown, Trash2, Search, Settings, X, ArrowDown, History, Folder, Archive, ChevronRight, FolderPlus, MessageSquarePlus } from "lucide-react";
import StrategiesView from "../views/StrategiesView";
import PortfoliosView from "../views/PortfoliosView";
import SettingsView from "../views/SettingsView";
import { ChatActionOption, Message, StrategyResultPayload } from "./types";

type StrategyId = "buy_and_hold" | "btfd" | "hodl" | "dca" | "moon_mission";

type StrategyDraft = {
  strategyId?: StrategyId;
  symbols: string[];
  startDate?: string;
  endDate?: string;
};

type StrategyDefinition = {
  id: StrategyId;
  label: string;
  aliases: string[];
  preset: {
    totalReturn: string;
    maxDrawdown: string;
    winRate: string;
    benchmark: string;
    cashValue: string;
    holdingPeriod: string;
  };
};

const EMPTY_DRAFT: StrategyDraft = {
  symbols: [],
};

const SUPPORTED_STRATEGIES: StrategyDefinition[] = [
  {
    id: "buy_and_hold",
    label: "Buy and Hold (Long Only)",
    aliases: ["buy and hold", "buy & hold", "long only"],
    preset: {
      totalReturn: "+18.6%",
      maxDrawdown: "14.2%",
      winRate: "61%",
      benchmark: "+4.3% vs S&P",
      cashValue: "$10k -> $27.1k",
      holdingPeriod: "8 months",
    },
  },
  {
    id: "btfd",
    label: "BTFD (Mean Reversion)",
    aliases: ["btfd", "mean reversion", "buy the dip"],
    preset: {
      totalReturn: "+15.9%",
      maxDrawdown: "9.8%",
      winRate: "67%",
      benchmark: "+2.8% vs S&P",
      cashValue: "$10k -> $24.8k",
      holdingPeriod: "5 months",
    },
  },
  {
    id: "hodl",
    label: "HODL (Long Term Trend)",
    aliases: ["hodl", "long term trend", "trend following"],
    preset: {
      totalReturn: "+20.4%",
      maxDrawdown: "12.1%",
      winRate: "64%",
      benchmark: "+3.9% vs S&P",
      cashValue: "$10k -> $29.0k",
      holdingPeriod: "11 months",
    },
  },
  {
    id: "dca",
    label: "DCA (Accumulation)",
    aliases: ["dca", "accumulation", "dollar cost averaging", "dollar-cost averaging"],
    preset: {
      totalReturn: "+13.7%",
      maxDrawdown: "7.6%",
      winRate: "70%",
      benchmark: "+2.1% vs S&P",
      cashValue: "$10k -> $22.9k",
      holdingPeriod: "9 months",
    },
  },
  {
    id: "moon_mission",
    label: "Moon Mission (Momentum Breakout)",
    aliases: ["moon mission", "to the moon", "momentum breakout", "moon"],
    preset: {
      totalReturn: "+23.0%",
      maxDrawdown: "11%",
      winRate: "68%",
      benchmark: "+5.0% vs S&P",
      cashValue: "$10k -> $31.4k",
      holdingPeriod: "6 months",
    },
  },
];

const NON_SYMBOL_TOKENS = new Set([
  "THE",
  "AND",
  "FOR",
  "WITH",
  "FROM",
  "TO",
  "RUN",
  "LONG",
  "ONLY",
  "HOLD",
  "HODL",
  "BTFD",
  "DCA",
  "MOON",
  "MISSION",
  "MEAN",
  "REVERSION",
  "MOMENTUM",
  "BREAKOUT",
  "BUY",
  "DIP",
  "STYLE",
  "STRATEGY",
  "START",
  "END",
  "DATE",
  "DATES",
  "TODAY",
  "THIS",
  "THAT",
  "NOW",
  "CRYPTO",
  "EQUITY",
  "EQUITIES",
]);

const STYLE_ACTIONS: ChatActionOption[] = [
  { id: "style-breakout", label: "I hunt breakouts", value: "I hunt breakouts" },
  { id: "style-indexer", label: "I am a long-term indexer", value: "I am a long-term indexer" },
  { id: "style-dips", label: "I buy dips", value: "I buy dips" },
  { id: "style-balanced", label: "I mix swing and long-term", value: "I mix swing and long-term" },
];

const STRATEGY_ACTIONS: ChatActionOption[] = SUPPORTED_STRATEGIES.map((strategy) => ({
  id: `strategy-${strategy.id}`,
  label: strategy.label.replace(" (Long Only)", ""),
  value: strategy.aliases[0],
}));

const SYMBOL_ACTIONS: ChatActionOption[] = [
  { id: "symbols-tech", label: "AAPL, MSFT, NVDA", value: "AAPL MSFT NVDA" },
  { id: "symbols-crypto", label: "BTC, ETH, SOL", value: "BTC ETH SOL" },
  { id: "symbols-index", label: "SPY, QQQ", value: "SPY QQQ" },
  { id: "symbols-manual", label: "I will type symbols", value: "I will type symbols" },
];

const DATE_ACTIONS: ChatActionOption[] = [
  { id: "dates-2020-2024", label: "2020 to 2024", value: "2020 to 2024" },
  { id: "dates-2022-2024", label: "2022 to 2024", value: "2022 to 2024" },
  { id: "dates-2024-2025", label: "2024-01-01 to 2025-12-31", value: "2024-01-01 to 2025-12-31" },
];

const RESULT_ACTIONS: ChatActionOption[] = [
  { id: "result-add", label: "Add strategy to portfolio", value: "/action:add-to-portfolio" },
  { id: "result-new", label: "Try a new strategy", value: "/action:new-strategy" },
];

const getStrategyDefinition = (id?: StrategyId) =>
  SUPPORTED_STRATEGIES.find((strategy) => strategy.id === id);

const detectStrategy = (text: string): StrategyId | undefined => {
  const normalized = text.toLowerCase();
  const match = SUPPORTED_STRATEGIES.find((strategy) =>
    strategy.aliases.some((alias) => normalized.includes(alias)),
  );
  return match?.id;
};

const extractSymbols = (text: string): string[] => {
  const candidates = text.toUpperCase().match(/\b[A-Z]{2,5}\b/g) ?? [];
  return [...new Set(candidates.filter((token) => !NON_SYMBOL_TOKENS.has(token)))];
};

const extractDateRange = (text: string): { startDate: string; endDate: string } | null => {
  const explicitRange = text.match(/(20\d{2}-\d{2}-\d{2})\s*(?:to|-)\s*(20\d{2}-\d{2}-\d{2})/i);
  if (explicitRange) {
    return { startDate: explicitRange[1], endDate: explicitRange[2] };
  }

  const allIsoDates = text.match(/20\d{2}-\d{2}-\d{2}/g);
  if (allIsoDates && allIsoDates.length >= 2) {
    return { startDate: allIsoDates[0], endDate: allIsoDates[1] };
  }

  const yearRange = text.match(/\b(20\d{2})\s*(?:to|-)\s*(20\d{2})\b/);
  if (yearRange) {
    return {
      startDate: `${yearRange[1]}-01-01`,
      endDate: `${yearRange[2]}-12-31`,
    };
  }

  return null;
};

const isValidDateOrder = (startDate?: string, endDate?: string) => {
  if (!startDate || !endDate) return true;
  return new Date(startDate).getTime() < new Date(endDate).getTime();
};

const mergeSymbols = (currentSymbols: string[], newSymbols: string[]) => [
  ...new Set([...currentSymbols, ...newSymbols]),
];

const buildDemoResultPayload = (draft: StrategyDraft): StrategyResultPayload => {
  const strategy = getStrategyDefinition(draft.strategyId) ?? SUPPORTED_STRATEGIES[0];
  const universe = draft.symbols.join(", ");
  return {
    strategyName: strategy.label,
    period: `${draft.startDate} to ${draft.endDate}`,
    metrics: [
      { label: "Total Return (%)", value: strategy.preset.totalReturn },
      { label: "Top / Bottom Performer", value: "NVDA (top), BYD (bottom)" },
      { label: "Cash Value ($)", value: strategy.preset.cashValue },
      { label: "Max Drawdown", value: strategy.preset.maxDrawdown },
      { label: "Benchmark", value: strategy.preset.benchmark },
      { label: "Holding Period", value: strategy.preset.holdingPeriod },
    ],
    benchmarkNote: `Universe: ${universe}. Demo engine runs long-only presets.`,
  };
};

const consumeActionPills = (messages: Message[]) => {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role === "ai" && message.actions && message.actions.length > 0) {
      return messages.map((entry, index) =>
        index === i ? { ...entry, actions: undefined } : entry,
      );
    }
  }
  return messages;
};

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const runTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const welcomeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [strategyDraft, setStrategyDraft] = useState<StrategyDraft>(EMPTY_DRAFT);
  const [profileStyle, setProfileStyle] = useState<string | null>(null);
  const [showWelcomeBacksplash, setShowWelcomeBacksplash] = useState(true);
  const [searchText, setSearchText] = useState("");
  const [isScrolledUp, setIsScrolledUp] = useState(false);
  const [isScrolling, setIsScrolling] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRecentsExpanded, setIsRecentsExpanded] = useState(true);
  const [currentView, setCurrentView] = useState<'chat' | 'strategies' | 'portfolios' | 'settings'>('chat');
  const [showHeaderMenu, setShowHeaderMenu] = useState(false);
  const [activeSubmenu, setActiveSubmenu] = useState<"none" | "history" | "portfolio">("none");

  const closeHeaderMenu = () => {
    setShowHeaderMenu(false);
    setActiveSubmenu("none");
  };

  const handleScrollEvent = (e: React.UIEvent<HTMLDivElement>) => {
    setIsScrolling(true);
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }
    scrollTimeoutRef.current = setTimeout(() => {
      setIsScrolling(false);
    }, 220);

    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    const distanceToBottom = scrollHeight - Math.ceil(scrollTop) - clientHeight;
    setIsScrolledUp(distanceToBottom > 200);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const startWelcomeFlow = () => {
    setShowWelcomeBacksplash(true);
    setMessages([]);
    if (welcomeTimeoutRef.current) {
      clearTimeout(welcomeTimeoutRef.current);
    }
    welcomeTimeoutRef.current = setTimeout(() => {
      setShowWelcomeBacksplash(false);
      setMessages([
        {
          id: Date.now().toString(),
          role: "ai",
          kind: "text",
          content:
            "Welcome to Argus. I can help you backtest strategies, compare results, and build portfolios. What is your investment or trading style?",
          actions: STYLE_ACTIONS,
        },
      ]);
    }, 3200);
  };

  useEffect(() => {
    const startupTimer = setTimeout(() => {
      startWelcomeFlow();
    }, 0);
    return () => {
      clearTimeout(startupTimer);
      if (runTimeoutRef.current) {
        clearTimeout(runTimeoutRef.current);
      }
      if (welcomeTimeoutRef.current) {
        clearTimeout(welcomeTimeoutRef.current);
      }
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSend = (text: string) => {
    if (!text.trim()) return;
    setShowWelcomeBacksplash(false);
    if (welcomeTimeoutRef.current) {
      clearTimeout(welcomeTimeoutRef.current);
    }

    const now = Date.now();
    const userId = now.toString();
    const aiId = (now + 1).toString();

    if (text === "/action:new-strategy") {
      const refreshedDraft: StrategyDraft = { ...EMPTY_DRAFT };
      setStrategyDraft(refreshedDraft);
      setMessages((prev) => [
        ...consumeActionPills(prev),
        { id: userId, role: "user", kind: "text", content: "Try a new strategy" },
        {
          id: aiId,
          role: "ai",
          kind: "text",
          content: "Perfect. Which strategy would you like to try next?",
          actions: STRATEGY_ACTIONS,
        },
      ]);
      return;
    }

    if (text === "/action:add-to-portfolio") {
      setMessages((prev) => [
        ...consumeActionPills(prev),
        { id: userId, role: "user", kind: "text", content: "Add strategy to portfolio" },
        {
          id: aiId,
          role: "ai",
          kind: "text",
          content: "Added to your demo portfolio. Want to test another strategy or symbols?",
          actions: [
            { id: "next-strategy", label: "Try a new strategy", value: "/action:new-strategy" },
            { id: "next-symbols", label: "Change symbols", value: "AAPL MSFT NVDA" },
          ],
        },
      ]);
      return;
    }

    const parsedStrategy = detectStrategy(text);
    const parsedSymbols = extractSymbols(text);
    const parsedDateRange = extractDateRange(text);
    const resolvedProfileStyle = profileStyle ?? text.trim();

    const nextDraft: StrategyDraft = {
      ...strategyDraft,
      strategyId: parsedStrategy ?? strategyDraft.strategyId,
      symbols: mergeSymbols(strategyDraft.symbols, parsedSymbols),
      startDate: parsedDateRange?.startDate ?? strategyDraft.startDate,
      endDate: parsedDateRange?.endDate ?? strategyDraft.endDate,
    };

    const hasTooManySymbols = nextDraft.symbols.length > 6;
    const hasInvalidDateOrder = !isValidDateOrder(nextDraft.startDate, nextDraft.endDate);
    const minimumReady = Boolean(
      nextDraft.strategyId &&
      nextDraft.symbols.length > 0 &&
      nextDraft.startDate &&
      nextDraft.endDate &&
      !hasTooManySymbols &&
      !hasInvalidDateOrder,
    );

    const newUserMsg: Message = { id: userId, role: "user", kind: "text", content: text };

    if (!profileStyle) {
      setProfileStyle(resolvedProfileStyle);
    }

    if (hasTooManySymbols) {
      setMessages((prev) => [
        ...consumeActionPills(prev),
        newUserMsg,
        {
          id: aiId,
          role: "ai",
          kind: "text",
          content: "Use up to 6 symbols only. Send a smaller list (equities and/or crypto).",
          actions: SYMBOL_ACTIONS,
        },
      ]);
      return;
    }

    if (hasInvalidDateOrder) {
      setMessages((prev) => [
        ...consumeActionPills(prev),
        newUserMsg,
        {
          id: aiId,
          role: "ai",
          kind: "text",
          content: "Your date range looks reversed. Send start date first, then end date.",
          actions: DATE_ACTIONS,
        },
      ]);
      return;
    }

    setStrategyDraft(nextDraft);

    if (!minimumReady) {
      const isShortRequest = /short|shorting|puts|put options|inverse/i.test(text);
      const missingStrategy = !nextDraft.strategyId;
      const missingSymbols = nextDraft.symbols.length === 0;
      const missingDates = !nextDraft.startDate || !nextDraft.endDate;

      let guidance = "";
      let actions: ChatActionOption[] | undefined;

      if (isShortRequest) {
        guidance = "Argus demo runs long-only strategies for now. Pick a long strategy and I will run it.";
        actions = STRATEGY_ACTIONS;
      } else if (missingStrategy) {
        guidance =
          profileStyle === null
            ? "That is a way to keep things interesting. Which strategy would you like to try first?"
            : "Which strategy would you like to try first?";
        actions = STRATEGY_ACTIONS;
      } else if (missingSymbols) {
        guidance = `Great pick: ${getStrategyDefinition(nextDraft.strategyId)?.label}. Choose up to 6 symbols or type your own.`;
        actions = SYMBOL_ACTIONS;
      } else if (missingDates) {
        guidance = `Locked: ${getStrategyDefinition(nextDraft.strategyId)?.label} on ${nextDraft.symbols.join(", ")}. Select a date range.`;
        actions = DATE_ACTIONS;
      }

      setMessages((prev) => [
        ...consumeActionPills(prev),
        newUserMsg,
        {
          id: aiId,
          role: "ai",
          kind: "text",
          content: guidance,
          actions,
        },
      ]);
      return;
    }

    const loadingAiMsg: Message = {
      id: aiId,
      role: "ai",
      kind: "strategy_result",
      content: "Let me crunch the numbers on that...",
      isLoadingResult: true,
    };

    setMessages((prev) => [...consumeActionPills(prev), newUserMsg, loadingAiMsg]);

    if (runTimeoutRef.current) {
      clearTimeout(runTimeoutRef.current);
    }
    runTimeoutRef.current = setTimeout(() => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiId
            ? {
                ...msg,
                isLoadingResult: false,
                content: undefined,
                result: buildDemoResultPayload(nextDraft),
                actions: RESULT_ACTIONS,
              }
            : msg,
        ),
      );
    }, 1100);
  };

  const handleAction = (value: string) => {
    handleSend(value);
  };

  return (
    <div className="relative w-full h-[100dvh] bg-[#f9f9f9] dark:bg-[#141517] overflow-hidden flex">
      <div className="absolute inset-y-0 left-0 w-full md:w-[320px] h-full flex flex-col pt-12 pb-8 px-6 z-0">
        <div className="flex items-center justify-between w-full mb-10">
           <h1 className="text-[26px] font-medium tracking-tight text-black dark:text-white" style={{ fontFamily: 'var(--font-space-grotesk)' }}>argus</h1>
           <button
             className="flex items-center justify-center p-2 rounded-xl border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-black dark:text-white"
             onClick={() => {
               setIsSidebarOpen(false);
               setCurrentView("chat");
               setStrategyDraft(EMPTY_DRAFT);
               setProfileStyle(null);
               startWelcomeFlow();
             }}
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

      {showWelcomeBacksplash && (
        <div className="absolute inset-0 z-[15] pointer-events-none flex items-center justify-center">
          <div className="flex flex-col items-center gap-5 px-6 animate-in fade-in duration-700">
            <p className="text-[22px] sm:text-[28px] font-medium tracking-tight text-black/80 dark:text-white/85">
              <span className="inline-block text-transparent bg-clip-text bg-[length:220%_100%] bg-gradient-to-r from-black/70 via-black to-black/70 dark:from-white/70 dark:via-white dark:to-white/70 animate-[argus_welcome_sweep_3.2s_ease-in-out_infinite] [filter:drop-shadow(0_0_0_rgba(255,255,255,0))] dark:[filter:drop-shadow(0_0_0_rgba(255,255,255,0))]">
                Welcome to argus
              </span>
              <span className="text-black/75 dark:text-white/82">, user.</span>
            </p>
            <svg
              viewBox="0 0 260 80"
              className="w-[220px] h-[54px] opacity-80 dark:opacity-95 animate-[argus_infinity_pulse_3.2s_ease-in-out_infinite]"
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="argusInfinityGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="currentColor" stopOpacity="0.18" />
                  <stop offset="50%" stopColor="currentColor" stopOpacity="0.95" />
                  <stop offset="100%" stopColor="currentColor" stopOpacity="0.18" />
                </linearGradient>
              </defs>
              <path
                d="M20 40 C40 10, 80 10, 120 40 C160 70, 200 70, 240 40 C200 10, 160 10, 120 40 C80 70, 40 70, 20 40 Z"
                fill="none"
                stroke="url(#argusInfinityGradient)"
                strokeWidth="2.25"
                className="text-black dark:text-white [filter:drop-shadow(0_0_7px_rgba(255,255,255,0.25))] dark:[filter:drop-shadow(0_0_9px_rgba(255,255,255,0.45))] [stroke-dasharray:330] animate-[argus_infinity_flow_4.2s_linear_infinite]"
              />
            </svg>
          </div>
        </div>
      )}

      <div className="absolute top-4 right-4 z-30">
        <button
          onClick={() => {
            if (showHeaderMenu) {
              closeHeaderMenu();
              return;
            }
            setShowHeaderMenu(true);
          }}
          className="flex items-center justify-center p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-black dark:text-white"
          title="Chat Options"
        >
          <History className="w-5 h-5" />
        </button>

        {showHeaderMenu && (
          <>
            <div
              className="fixed inset-0 bg-black/20 dark:bg-black/80 md:bg-transparent z-40 animate-in fade-in duration-300 md:duration-0"
              onClick={closeHeaderMenu}
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
                    onClick={() => {
                      closeHeaderMenu();
                      setCurrentView("chat");
                      setStrategyDraft(EMPTY_DRAFT);
                      setProfileStyle(null);
                      startWelcomeFlow();
                    }}
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
                    onClick={closeHeaderMenu}
                  >
                    <Archive className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                    Archive
                  </button>

                  <div className="h-px w-full bg-black/5 dark:bg-white/5 my-2 md:my-1" />

                  <button
                    className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-red-500/10 transition-colors text-left text-red-500 text-[16px] md:text-[15px] font-medium"
                    onClick={() => {
                      closeHeaderMenu();
                      setStrategyDraft(EMPTY_DRAFT);
                      setProfileStyle(null);
                      startWelcomeFlow();
                    }}
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
                      <button className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium" onClick={closeHeaderMenu}>
                        <FolderPlus className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                        New portfolio
                      </button>
                      <button className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium" onClick={closeHeaderMenu}>
                        <Folder className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                        Alpha Volatility &apos;24
                      </button>
                      <button className="w-full flex items-center gap-4 px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[16px] md:text-[15px] font-medium" onClick={closeHeaderMenu}>
                        <Folder className="w-[18px] h-[18px] md:w-4 md:h-4 text-black/60 dark:text-white/60" />
                        Tech Breakouts Q3
                      </button>
                    </div>
                  )}

                  {/* History Options */}
                  {activeSubmenu === 'history' && (
                    <div className="flex flex-col animate-in fade-in zoom-in-95 duration-200 delay-100 fill-mode-both">
                      <button className="w-full flex flex-col justify-center px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left cursor-pointer" onClick={closeHeaderMenu}>
                        <div className="flex justify-between items-center w-full">
                          <span className="text-black dark:text-white text-[16px] md:text-[15px] font-medium truncate pr-2">Short BTC Volatility</span>
                          <span className="text-[14px] md:text-[12px] text-black/40 dark:text-white/40 shrink-0">Today</span>
                        </div>
                        <span className="text-[14px] md:text-[13px] text-black/50 dark:text-white/50 truncate w-full mt-1 md:mt-0.5">Parameters: 50d SMA, Take Profit 10%...</span>
                      </button>
                      <div className="h-px w-[85%] mx-auto bg-black/5 dark:bg-white/5 my-1 md:my-0" />
                      <button className="w-full flex flex-col justify-center px-6 md:px-5 py-4 md:py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left cursor-pointer" onClick={closeHeaderMenu}>
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
        data-scrolling={isScrolling ? "true" : "false"}
        className="argus-scrollbar flex-1 overflow-y-auto px-4 pt-[86px] pb-[120px] space-y-8 scroll-smooth transition-colors duration-300"
      >
        <div
          className={`transition-[height,opacity] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
            messages.length <= 1 ? "h-[26vh] opacity-100" : messages.length <= 2 ? "h-[14vh] opacity-70" : "h-0 opacity-0"
          }`}
          aria-hidden="true"
        />
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} onAction={handleAction} />
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
