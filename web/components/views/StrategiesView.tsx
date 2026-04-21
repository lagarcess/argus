"use client";

import { useState, useRef, useEffect } from "react";
import { Menu, Plus, ChevronDown, Trash2, Pin, Edit2, Search, Settings, X } from "lucide-react";

type Strategy = {
  id: string;
  name: string;
  dateStr: string;
  isPinned?: boolean;
  assets: Array<{ 
    ticker: string; 
    name: string; 
    overallProfit: { value: string; isPositive: boolean };
    maxDrawdown: { value: string; isPositive: boolean };
    winRate: { value: string; isPositive: boolean };
  }>;
};

const MOCK_STRATEGIES: Strategy[] = [
  {
    id: "1",
    name: "Emerging Tech Alpha",
    dateStr: "today",
    assets: [
      { ticker: "XYZ", name: "Block", overallProfit: { value: "+8.5%", isPositive: true }, maxDrawdown: { value: "-1.8%", isPositive: false }, winRate: { value: "+42.5%", isPositive: true } },
      { ticker: "BTC", name: "Bitcoin", overallProfit: { value: "+103.5%", isPositive: true }, maxDrawdown: { value: "-21.7%", isPositive: false }, winRate: { value: "-21.7%", isPositive: false } },
      { ticker: "SOFI", name: "SoFi Tech", overallProfit: { value: "+18.4%", isPositive: true }, maxDrawdown: { value: "-8.4%", isPositive: false }, winRate: { value: "+54.5%", isPositive: true } },
      { ticker: "AFRM", name: "Affirm", overallProfit: { value: "-2.1%", isPositive: false }, maxDrawdown: { value: "-12.0%", isPositive: false }, winRate: { value: "-8.2%", isPositive: false } },
      { ticker: "PLTR", name: "Palantir", overallProfit: { value: "+24.5%", isPositive: true }, maxDrawdown: { value: "-2.1%", isPositive: false }, winRate: { value: "+68.2%", isPositive: true } },
      { ticker: "RBLX", name: "Roblox", overallProfit: { value: "+8.2%", isPositive: true }, maxDrawdown: { value: "-15.4%", isPositive: false }, winRate: { value: "+30.1%", isPositive: true } },
    ]
  },
  {
    id: "2",
    name: "Grid Trading Alg",
    dateStr: "today",
    assets: [
      { ticker: "ETH", name: "Ethereum", overallProfit: { value: "+22.4%", isPositive: true }, maxDrawdown: { value: "-18.5%", isPositive: false }, winRate: { value: "+45.2%", isPositive: true } },
      { ticker: "SOL", name: "Solana", overallProfit: { value: "+45.1%", isPositive: true }, maxDrawdown: { value: "-30.2%", isPositive: false }, winRate: { value: "+58.1%", isPositive: true } },
    ]
  },
  {
    id: "3",
    name: "Momentum Breakout",
    dateStr: "yesterday",
    assets: [
      { ticker: "NVDA", name: "NVIDIA", overallProfit: { value: "+84.2%", isPositive: true }, maxDrawdown: { value: "-4.2%", isPositive: false }, winRate: { value: "+75.0%", isPositive: true } },
      { ticker: "AMD", name: "AMD Inc.", overallProfit: { value: "-12.5%", isPositive: false }, maxDrawdown: { value: "-24.1%", isPositive: false }, winRate: { value: "+32.4%", isPositive: true } },
    ]
  },
  {
    id: "4",
    name: "Pairs Trading (ETH/BTC)",
    dateStr: "Oct 10, 2024",
    assets: [
      { ticker: "ETH-BTC", name: "Ratio", overallProfit: { value: "+2.1%", isPositive: true }, maxDrawdown: { value: "-1.5%", isPositive: false }, winRate: { value: "+52.1%", isPositive: true } },
    ]
  },
  {
    id: "5",
    name: "StatArb FinTech",
    dateStr: "Sep 29, 2024",
    assets: [
      { ticker: "HOOD", name: "Robinhood", overallProfit: { value: "-8.4%", isPositive: false }, maxDrawdown: { value: "-18.2%", isPositive: false }, winRate: { value: "+42.1%", isPositive: true } },
      { ticker: "COIN", name: "Coinbase", overallProfit: { value: "+15.3%", isPositive: true }, maxDrawdown: { value: "-25.4%", isPositive: false }, winRate: { value: "+55.3%", isPositive: true } },
    ]
  },
  {
    id: "6",
    name: "Volatility Harvester",
    dateStr: "Sep 14, 2024",
    assets: [
      { ticker: "VIXY", name: "ProShares VIX", overallProfit: { value: "-42.1%", isPositive: false }, maxDrawdown: { value: "-65.4%", isPositive: false }, winRate: { value: "+18.4%", isPositive: true } },
    ]
  },
  {
    id: "7",
    name: "Options Selling Q3",
    dateStr: "Aug 30, 2024",
    assets: [
      { ticker: "SPY", name: "S&P 500 ETF", overallProfit: { value: "+4.1%", isPositive: true }, maxDrawdown: { value: "-1.2%", isPositive: false }, winRate: { value: "+82.4%", isPositive: true } },
      { ticker: "QQQ", name: "Invesco QQQ", overallProfit: { value: "+6.8%", isPositive: true }, maxDrawdown: { value: "-2.4%", isPositive: false }, winRate: { value: "+78.1%", isPositive: true } },
    ]
  }
];

type StrategiesViewProps = {
  onMenuClick: () => void;
  onSettingsClick?: () => void;
};

export default function StrategiesView({ onMenuClick, onSettingsClick }: StrategiesViewProps) {
  const [strategies, setStrategies] = useState<Strategy[]>(MOCK_STRATEGIES);
  const [expandedId, setExpandedId] = useState<string | null>("1");
  const [activeContextMenu, setActiveContextMenu] = useState<string | null>(null);
  const [isScrolling, setIsScrolling] = useState(false);
  const [scrollIndicator, setScrollIndicator] = useState({ top: 0, height: 0, visible: false });

  // Simple Long Press logic
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleScrollActivity = (e: React.UIEvent<HTMLDivElement>) => {
    setIsScrolling(true);
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }
    scrollTimeoutRef.current = setTimeout(() => {
      setIsScrolling(false);
    }, 220);
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    if (scrollHeight > clientHeight) {
      const thumbHeight = Math.max((clientHeight / scrollHeight) * clientHeight, 28);
      const maxTop = clientHeight - thumbHeight;
      const top = (scrollTop / Math.max(scrollHeight - clientHeight, 1)) * maxTop;
      setScrollIndicator({ top, height: thumbHeight, visible: true });
    } else {
      setScrollIndicator({ top: 0, height: 0, visible: false });
    }
  };

  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);
  
  const handlePointerDown = (id: string, e: React.PointerEvent) => {
    // Only trigger long press if not clicking the chevron directly
    if ((e.target as HTMLElement).closest('.ignore-long-press')) return;
    
    timerRef.current = setTimeout(() => {
      setActiveContextMenu(id);
      if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate(50); // Haptic feedback if supported
      }
    }, 500);
  };

  const handlePointerUp = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  };

  const deleteStrategy = (id: string) => {
    setStrategies(strategies.filter(s => s.id !== id));
    setActiveContextMenu(null);
  };

  const togglePinStrategy = (id: string) => {
    setStrategies(strategies.map(s => s.id === id ? { ...s, isPinned: !s.isPinned } : s));
    setActiveContextMenu(null);
  };

  const sortedStrategies = [...strategies].sort((a, b) => {
    if (a.isPinned && !b.isPinned) return -1;
    if (!a.isPinned && b.isPinned) return 1;
    return parseInt(a.id) - parseInt(b.id);
  });

  const [searchText, setSearchText] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);

  const handleRename = (id: string, newName: string) => {
    setStrategies(strategies.map(s => s.id === id ? { ...s, name: newName } : s));
    setEditingId(null);
  };

  return (
    <div className="flex flex-col w-full h-[100dvh] max-w-3xl mx-auto overflow-hidden bg-[#f9f9f9] dark:bg-[#141517] relative">
      {/* Header */}
      <div className="absolute top-0 inset-x-0 h-28 z-30 pointer-events-none backdrop-blur-[8px] bg-[#f5f5f5]/10 dark:bg-[#191c1f]/20 [mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)]" />
      
      <div className="absolute top-4 left-4 z-[35]">
        <button 
          onClick={onMenuClick} 
          className="flex items-center justify-center p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-black dark:text-white border border-black/10 dark:border-white/10"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      <div className="absolute top-6 inset-x-0 w-full flex justify-center z-[35] pointer-events-none">
        <h1 className="text-[18px] font-medium tracking-tight pointer-events-auto">Strategies</h1>
      </div>

      <div className="absolute top-4 right-4 z-[35]">
        <button className="flex items-center justify-center p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-black dark:text-white">
          <Plus className="w-5 h-5" />
        </button>
      </div>

      {activeContextMenu && (
        <div 
          className="fixed inset-0 z-40 touch-none pointer-events-auto" 
          onPointerDown={(e) => { e.stopPropagation(); setActiveContextMenu(null); e.preventDefault(); }}
          onTouchStart={(e) => { e.stopPropagation(); setActiveContextMenu(null); }}
        />
      )}

      {/* List Content */}
      <div className="relative flex-1 min-h-0">
      <div
        onScroll={handleScrollActivity}
        className="argus-scrollbar h-full overflow-y-auto px-6 pt-24 pb-32"
      >
        <div className="flex flex-col gap-4">
          {sortedStrategies.map((strategy) => {
            const isExpanded = expandedId === strategy.id;
            const isContextOpen = activeContextMenu === strategy.id;

            return (
              <div key={strategy.id} className="flex flex-col">
                <div 
                  className={`relative flex flex-col w-full bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 overflow-hidden transition-all duration-300 ${isExpanded ? 'rounded-[24px]' : 'rounded-[24px]'} ${isContextOpen ? 'scale-[0.98] shadow-inner bg-black/5 z-50' : 'shadow-sm z-10'}`}
                  onPointerDown={(e) => handlePointerDown(strategy.id, e)}
                  onPointerUp={handlePointerUp}
                  onPointerLeave={handlePointerUp}
                  onPointerCancel={handlePointerUp}
                  onTouchMove={handlePointerUp}
                  onContextMenu={(e) => e.preventDefault()} // prevent default mobile long-press context menu
                >
                  {/* Item Header */}
                  <div className="flex items-center justify-between p-5 select-none touch-none">
                    {editingId === strategy.id ? (
                      <input
                        type="text"
                        defaultValue={strategy.name}
                        autoFocus
                        onBlur={(e) => handleRename(strategy.id, e.target.value.trim() || strategy.name)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRename(strategy.id, e.currentTarget.value.trim() || strategy.name);
                          if (e.key === 'Escape') setEditingId(null);
                        }}
                        className="text-[18px] font-medium text-black dark:text-white bg-transparent border-b border-black/20 dark:border-white/20 focus:outline-none focus:border-black dark:focus:border-white pointer-events-auto"
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span className="text-[18px] font-medium text-black dark:text-white flex items-center gap-2">
                        {strategy.name}
                        {strategy.isPinned && <Pin className="w-3.5 h-3.5 text-black/40 dark:text-white/40 fill-black/40 dark:fill-white/40" style={{ transform: 'rotate(45deg)' }} />}
                      </span>
                    )}
                    <button 
                      onClick={(e) => { e.stopPropagation(); setExpandedId(isExpanded ? null : strategy.id); }}
                      className="ignore-long-press flex items-center justify-center w-8 h-8 rounded-[8px] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                    >
                      <ChevronDown className={`w-5 h-5 text-black/40 dark:text-white/40 transition-transform duration-200 ${isExpanded ? 'rotate-0' : '-rotate-90'}`} />
                    </button>
                  </div>

                  {/* Context Menu Overlay (Long Press) */}
                  {isContextOpen && (
                    <>
                      <div className="absolute top-0 inset-x-0 h-[72px] z-50 animate-in fade-in zoom-in-95 duration-200 bg-white dark:bg-[#1f2225] flex items-center justify-center gap-4 px-2 py-0 border-b border-black/10 dark:border-white/10 rounded-t-[24px]">
                        <button onClick={() => togglePinStrategy(strategy.id)} className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity">
                          <div className="w-10 h-10 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center"><Pin className="w-4 h-4" /></div>
                          <span className="text-[11px] font-medium tracking-tight">{strategy.isPinned ? "Unpin" : "Pin"}</span>
                        </button>
                        <button onClick={() => { setActiveContextMenu(null); setEditingId(strategy.id); }} className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity">
                          <div className="w-10 h-10 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center"><Edit2 className="w-4 h-4" /></div>
                          <span className="text-[11px] font-medium tracking-tight">Rename</span>
                        </button>
                        <button onClick={() => deleteStrategy(strategy.id)} className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity text-red-500">
                          <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center"><Trash2 className="w-4 h-4" /></div>
                          <span className="text-[11px] font-medium tracking-tight">Delete</span>
                        </button>
                        
                        {/* Close trigger layer */}
                        <div className="absolute inset-x-0 bottom-[-16px] h-4 flex justify-center items-center opacity-50 text-[9px] tracking-widest uppercase pointer-events-none drop-shadow-sm">Tap elsewhere to cancel</div>
                      </div>
                    </>
                  )}

                  {/* Expanded Content Grid */}
                  <div
                    className={`argus-scrollbar overflow-y-auto transition-all duration-300 ease-in-out relative ${isExpanded ? 'max-h-[220px] border-t border-black/5 dark:border-white/5' : 'max-h-0'}`}
                  >
                    <div className="flex flex-col px-5 py-4 gap-4">
                      
                      {/* Header Row (Sticky) */}
                      {strategy.assets.length > 0 && (
                        <div className="grid grid-cols-4 gap-2 items-end pb-2 sticky top-[-1px] bg-white dark:bg-[#1f2225] z-10 pt-1 -mt-1 shadow-[0_4px_10px_-5px_rgba(0,0,0,0.1)] dark:shadow-[0_4px_10px_-5px_rgba(0,0,0,0.5)]">
                          <div className="col-span-1"></div>
                          <div className="col-span-1 flex flex-col items-center justify-center">
                            <span className="text-[10px] lowercase font-medium text-black/40 dark:text-white/40 tracking-normal text-center leading-tight">overall profit</span>
                          </div>
                          <div className="col-span-1 flex flex-col items-center justify-center">
                            <span className="text-[10px] lowercase font-medium text-black/40 dark:text-white/40 tracking-normal text-center leading-tight">max drawdown</span>
                          </div>
                          <div className="col-span-1 flex flex-col items-center justify-center">
                            <span className="text-[10px] lowercase font-medium text-black/40 dark:text-white/40 tracking-normal text-center leading-tight">win rate</span>
                          </div>
                        </div>
                      )}

                      {/* Data Rows */}
                      {strategy.assets.map((asset, idx) => (
                        <div key={idx} className="grid grid-cols-4 gap-2 items-center">
                          {/* Asset Info */}
                          <div className="col-span-1 flex flex-col pl-1">
                            <span className="text-[16px] font-medium text-black dark:text-white tracking-tight">{asset.ticker}</span>
                            <span className="text-[11px] text-black/50 dark:text-white/50 truncate pr-2">{asset.name}</span>
                          </div>

                          {/* Overall Profit Pill */}
                          <div className="col-span-1 flex items-center justify-center">
                            <div className={`flex items-center justify-center w-full py-1.5 px-1 rounded-[8px] border text-[12px] font-medium tracking-tight ${asset.overallProfit.isPositive ? 'bg-green-500/10 text-green-600 border-green-500/20' : 'bg-red-500/10 text-red-600 border-red-500/20'}`}>
                              {asset.overallProfit.value}
                            </div>
                          </div>

                          {/* Max Drawdown Pill */}
                          <div className="col-span-1 flex items-center justify-center">
                            <div className={`flex items-center justify-center w-full py-1.5 px-1 rounded-[8px] border text-[12px] font-medium tracking-tight ${asset.maxDrawdown.isPositive ? 'bg-green-500/10 text-green-600 border-green-500/20' : 'bg-red-500/10 text-red-600 border-red-500/20'}`}>
                              {asset.maxDrawdown.value}
                            </div>
                          </div>
                          
                          {/* Win Rate Pill */}
                          <div className="col-span-1 flex items-center justify-center">
                            <div className={`flex items-center justify-center w-full py-1.5 px-1 rounded-[8px] border text-[12px] font-medium tracking-tight ${asset.winRate.isPositive ? 'bg-green-500/10 text-green-600 border-green-500/20' : 'bg-red-500/10 text-red-600 border-red-500/20'}`}>
                              {asset.winRate.value}
                            </div>
                          </div>
                        </div>
                      ))}

                    </div>
                  </div>
                </div>
                
                {/* Date Subtitle */}
                <span className="text-[12px] text-black/40 dark:text-white/40 mt-2 px-2">{strategy.dateStr}</span>
              </div>
            );
          })}
        </div>
      </div>
      {scrollIndicator.visible && (
        <div
          className={`absolute right-[2px] top-0 w-px rounded-full argus-scroll-indicator pointer-events-none ${isScrolling ? "opacity-100" : "opacity-0"}`}
          style={{ height: `${scrollIndicator.height}px`, transform: `translateY(${scrollIndicator.top}px)` }}
          aria-hidden="true"
        />
      )}
      </div>
      
      {/* Progressive Bottom Glass Blur Layer */}
      <div className="absolute bottom-0 inset-x-0 h-40 z-10 pointer-events-none backdrop-blur-[0.8px] bg-[#f9f9f9]/10 dark:bg-[#141517]/20 [mask-image:linear-gradient(to_top,black_50%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_top,black_50%,transparent_100%)]" />

      {/* Dormant Bottom Menu */}
      <div className="absolute bottom-6 inset-x-0 w-full px-4 z-20 pointer-events-none">
        <div className="pointer-events-auto max-w-3xl mx-auto flex items-center gap-4 transition-all duration-300 opacity-50 hover:opacity-100 focus-within:opacity-100 group">
          <button onClick={onSettingsClick} className="flex items-center justify-center w-[52px] h-[52px] rounded-full border border-black/10 dark:border-white/10 bg-white/50 dark:bg-[#1f2225]/50 backdrop-blur-xl hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-black dark:text-white shrink-0 shadow-lg" title="Settings">
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

    </div>
  );
}
