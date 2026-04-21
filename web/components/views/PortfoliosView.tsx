"use client";

import { useState, useRef } from "react";
import { Menu, Plus, ChevronDown, Trash2, Pin, Edit2, Briefcase, Search, Settings, X } from "lucide-react";

type Portfolio = {
  id: string;
  name: string;
  dateStr: string;
  isPinned?: boolean;
  stats: {
    capital: string;
    topPerformer: string;
    vsBenchmark: { value: string; isPositive: boolean };
    totalAssets: string;
    diversificationRatio: { value: string; isPositive: boolean };
    correlationRatio: string;
  } | null;
};

const MOCK_PORTFOLIOS: Portfolio[] = [
  {
    id: "1",
    name: "Tech Breakouts Q3",
    dateStr: "today",
    stats: { capital: "$ 14,500", topPerformer: "NVDA", vsBenchmark: { value: "+12.4%", isPositive: true }, totalAssets: "8", diversificationRatio: { value: "+20%", isPositive: true }, correlationRatio: "-0.1" }
  },
  {
    id: "2",
    name: "Crypto Moon Mission",
    dateStr: "today",
    stats: { capital: "$ 4,250", topPerformer: "SOL", vsBenchmark: { value: "+45.2%", isPositive: true }, totalAssets: "4", diversificationRatio: { value: "+15%", isPositive: true }, correlationRatio: "0.2" }
  },
  {
    id: "3",
    name: "Dividend Aristocrats",
    dateStr: "yesterday",
    stats: { capital: "$ 35,000", topPerformer: "PEP", vsBenchmark: { value: "-1.2%", isPositive: false }, totalAssets: "15", diversificationRatio: { value: "+30%", isPositive: true }, correlationRatio: "0.8" }
  },
  {
    id: "4",
    name: "Defensive Rotation",
    dateStr: "Oct 28, 2024",
    stats: { capital: "$ 8,900", topPerformer: "LMT", vsBenchmark: { value: "+2.1%", isPositive: true }, totalAssets: "6", diversificationRatio: { value: "+18%", isPositive: true }, correlationRatio: "0.5" }
  },
  {
    id: "5",
    name: "AI Infrastructure",
    dateStr: "Oct 15, 2024",
    stats: { capital: "$ 24,000", topPerformer: "AMD", vsBenchmark: { value: "+18.5%", isPositive: true }, totalAssets: "5", diversificationRatio: { value: "-5%", isPositive: false }, correlationRatio: "0.9" }
  },
  {
    id: "6",
    name: "Global Macro",
    dateStr: "Sep 20, 2024",
    stats: { capital: "$ 52,100", topPerformer: "GLD", vsBenchmark: { value: "+4.5%", isPositive: true }, totalAssets: "12", diversificationRatio: { value: "+25%", isPositive: true }, correlationRatio: "0.1" }
  },
  {
    id: "7",
    name: "Short BTC Volatility",
    dateStr: "Sep 05, 2024",
    stats: { capital: "$ 15,000", topPerformer: "USDC", vsBenchmark: { value: "+8.9%", isPositive: true }, totalAssets: "2", diversificationRatio: { value: "-10%", isPositive: false }, correlationRatio: "0.0" }
  },
  {
    id: "8",
    name: "Web3 Gaming",
    dateStr: "Aug 12, 2024",
    stats: { capital: "$ 3,200", topPerformer: "IMX", vsBenchmark: { value: "-12.4%", isPositive: false }, totalAssets: "7", diversificationRatio: { value: "+8%", isPositive: true }, correlationRatio: "0.6" }
  },
  {
    id: "9",
    name: "Biotech Catalyst",
    dateStr: "Jul 04, 2024",
    stats: { capital: "$ 9,500", topPerformer: "CRSP", vsBenchmark: { value: "+34.2%", isPositive: true }, totalAssets: "5", diversificationRatio: { value: "-12%", isPositive: false }, correlationRatio: "0.4" }
  },
  {
    id: "10",
    name: "Emerging Markets",
    dateStr: "May 22, 2024",
    stats: { capital: "$ 18,400", topPerformer: "EEM", vsBenchmark: { value: "-4.2%", isPositive: false }, totalAssets: "10", diversificationRatio: { value: "+22%", isPositive: true }, correlationRatio: "0.7" }
  }
];

type PortfoliosViewProps = {
  onMenuClick: () => void;
  onSettingsClick?: () => void;
};

export default function PortfoliosView({ onMenuClick, onSettingsClick }: PortfoliosViewProps) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>(MOCK_PORTFOLIOS);
  const [expandedId, setExpandedId] = useState<string | null>("1");
  const [activeContextMenu, setActiveContextMenu] = useState<string | null>(null);

  const timerRef = useRef<NodeJS.Timeout | null>(null);
  
  const handlePointerDown = (id: string, e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('.ignore-long-press')) return;
    timerRef.current = setTimeout(() => {
      setActiveContextMenu(id);
      if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate(50);
      }
    }, 500);
  };

  const handlePointerUp = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  };

  const deletePortfolio = (id: string) => {
    setPortfolios(portfolios.filter(p => p.id !== id));
    setActiveContextMenu(null);
  };

  const togglePinPortfolio = (id: string) => {
    setPortfolios(portfolios.map(p => p.id === id ? { ...p, isPinned: !p.isPinned } : p));
    setActiveContextMenu(null);
  };

  const sortedPortfolios = [...portfolios].sort((a, b) => {
    if (a.isPinned && !b.isPinned) return -1;
    if (!a.isPinned && b.isPinned) return 1;
    return parseInt(a.id) - parseInt(b.id);
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");

  const handleRename = (id: string, newName: string) => {
    setPortfolios(portfolios.map(p => p.id === id ? { ...p, name: newName } : p));
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
        <h1 className="text-[18px] font-medium tracking-tight pointer-events-auto">Portfolios</h1>
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
      <div className="flex-1 overflow-y-auto px-6 pt-24 pb-32">
        <div className="flex flex-col gap-4">
          {sortedPortfolios.map((portfolio) => {
            const isExpanded = expandedId === portfolio.id;
            const isContextOpen = activeContextMenu === portfolio.id;

            return (
              <div key={portfolio.id} className="flex flex-col">
                <div 
                  className={`relative flex flex-col w-full bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 overflow-hidden transition-all duration-300 ${isExpanded ? 'rounded-[24px]' : 'rounded-[24px]'} ${isContextOpen ? 'scale-[0.98] shadow-inner bg-black/5 z-50' : 'shadow-sm z-10'}`}
                  onPointerDown={(e) => handlePointerDown(portfolio.id, e)}
                  onPointerUp={handlePointerUp}
                  onPointerLeave={handlePointerUp}
                  onPointerCancel={handlePointerUp}
                  onTouchMove={handlePointerUp}
                  onContextMenu={(e) => e.preventDefault()}
                >
                  {/* Item Header */}
                  <div className="flex items-center justify-between p-5 select-none touch-none">
                    {editingId === portfolio.id ? (
                      <input
                        type="text"
                        defaultValue={portfolio.name}
                        autoFocus
                        onBlur={(e) => handleRename(portfolio.id, e.target.value.trim() || portfolio.name)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRename(portfolio.id, e.currentTarget.value.trim() || portfolio.name);
                          if (e.key === 'Escape') setEditingId(null);
                        }}
                        className="text-[18px] font-medium text-black dark:text-white bg-transparent border-b border-black/20 dark:border-white/20 focus:outline-none focus:border-black dark:focus:border-white pointer-events-auto w-full mr-4"
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span className="text-[18px] font-medium text-black dark:text-white flex items-center gap-2">
                        {portfolio.name}
                        {portfolio.isPinned && <Pin className="w-3.5 h-3.5 text-black/40 dark:text-white/40 fill-black/40 dark:fill-white/40" style={{ transform: 'rotate(45deg)' }} />}
                      </span>
                    )}
                    <button 
                      onClick={(e) => { e.stopPropagation(); setExpandedId(isExpanded ? null : portfolio.id); }}
                      className="ignore-long-press flex items-center justify-center w-8 h-8 rounded-[8px] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                    >
                      <ChevronDown className={`w-5 h-5 text-black/40 dark:text-white/40 transition-transform duration-200 ${isExpanded ? 'rotate-0' : '-rotate-90'}`} />
                    </button>
                  </div>

                  {/* Context Menu Overlay */}
                  {isContextOpen && (
                    <>
                      <div className="absolute top-0 inset-x-0 h-[72px] z-50 animate-in fade-in zoom-in-95 duration-200 bg-white dark:bg-[#1f2225] flex items-center justify-center gap-4 px-2 py-0 border-b border-black/10 dark:border-white/10 rounded-t-[24px]">
                        <button onClick={() => togglePinPortfolio(portfolio.id)} className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity">
                          <div className="w-10 h-10 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center"><Pin className="w-4 h-4" /></div>
                          <span className="text-[11px] font-medium tracking-tight">{portfolio.isPinned ? "Unpin" : "Pin"}</span>
                        </button>
                        <button onClick={() => { setActiveContextMenu(null); setEditingId(portfolio.id); }} className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity">
                          <div className="w-10 h-10 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center"><Edit2 className="w-4 h-4" /></div>
                          <span className="text-[11px] font-medium tracking-tight">Rename</span>
                        </button>
                        <button onClick={() => deletePortfolio(portfolio.id)} className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity text-red-500">
                          <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center"><Trash2 className="w-4 h-4" /></div>
                          <span className="text-[11px] font-medium tracking-tight">Delete</span>
                        </button>
                        
                        <div className="absolute inset-x-0 bottom-[-16px] h-4 flex justify-center items-center opacity-50 text-[9px] tracking-widest uppercase pointer-events-none drop-shadow-sm">Tap elsewhere to cancel</div>
                      </div>
                    </>
                  )}

                  {/* Expanded Content Grid */}
                  <div className={`overflow-hidden transition-all duration-300 ease-in-out ${isExpanded ? 'max-h-[300px] border-t border-black/5 dark:border-white/5' : 'max-h-0'}`}>
                    {portfolio.stats && (
                      <div className="grid grid-cols-3 gap-y-6 gap-x-2 px-5 py-6">
                        
                        {/* Row 1 */}
                        <div className="flex flex-col items-center gap-1.5">
                          <div className="w-full py-2 px-1 rounded-[8px] border border-black/10 dark:border-white/10 text-center text-[15px] font-medium text-black dark:text-white bg-black/5 dark:bg-white/5">
                            {portfolio.stats.capital}
                          </div>
                          <span className="text-[11px] text-black/50 dark:text-white/50 font-medium">capital</span>
                        </div>

                        <div className="flex flex-col items-center gap-1.5">
                          <div className="w-full py-2 px-1 rounded-[8px] border border-black/10 dark:border-white/10 text-center text-[15px] font-medium text-black dark:text-white bg-black/5 dark:bg-white/5">
                            {portfolio.stats.topPerformer}
                          </div>
                          <span className="text-[11px] text-black/50 dark:text-white/50 font-medium whitespace-nowrap">top performer</span>
                        </div>

                        <div className="flex flex-col items-center gap-1.5">
                          <div className={`w-full py-2 px-1 rounded-[8px] border text-center text-[15px] font-medium tracking-tight ${portfolio.stats.vsBenchmark.isPositive ? 'bg-green-500/10 text-green-600 border-green-500/20' : 'bg-red-500/10 text-red-600 border-red-500/20'}`}>
                            {portfolio.stats.vsBenchmark.value}
                          </div>
                          <span className="text-[11px] text-black/50 dark:text-white/50 font-medium whitespace-nowrap">vs benchmark</span>
                        </div>

                        {/* Row 2 */}
                        <div className="flex flex-col items-center gap-1.5">
                          <div className="w-full py-2 px-1 rounded-[8px] border border-black/10 dark:border-white/10 text-center text-[15px] font-medium text-black dark:text-white bg-black/5 dark:bg-white/5">
                            {portfolio.stats.totalAssets}
                          </div>
                          <span className="text-[11px] text-black/50 dark:text-white/50 font-medium whitespace-nowrap">total assets</span>
                        </div>

                        <div className="flex flex-col items-center gap-1.5">
                          <div className={`w-full py-2 px-1 rounded-[8px] border text-center text-[15px] font-medium tracking-tight ${portfolio.stats.diversificationRatio.isPositive ? 'bg-green-500/10 text-green-600 border-green-500/20' : 'bg-red-500/10 text-red-600 border-red-500/20'}`}>
                            {portfolio.stats.diversificationRatio.value}
                          </div>
                          <span className="text-[11px] text-center text-black/50 dark:text-white/50 font-medium whitespace-nowrap truncate w-full">diversification ratio</span>
                        </div>

                        <div className="flex flex-col items-center gap-1.5">
                          <div className="w-full py-2 px-1 rounded-[8px] border border-black/10 dark:border-white/10 text-center text-[15px] font-medium text-black dark:text-white bg-black/5 dark:bg-white/5">
                            {portfolio.stats.correlationRatio}
                          </div>
                          <span className="text-[11px] text-center text-black/50 dark:text-white/50 font-medium whitespace-nowrap truncate w-full">correlation ratio</span>
                        </div>

                      </div>
                    )}
                  </div>
                </div>
                
                <span className="text-[12px] text-black/40 dark:text-white/40 mt-2 px-2">{portfolio.dateStr}</span>
              </div>
            );
          })}
        </div>
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
                 className="absolute right-4 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-full bg-black/10 dark:bg-white/10 text-black/60 dark:text-white/60 hover:bg-black/20 dark:hover:bg-white/20 transition-colors pointer-events-auto"
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
