'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Search, X, Globe, Coins, LineChart, Plus } from 'lucide-react';
import { ASSET_REGISTRY, AssetRegistryItem } from '@/lib/assets';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

interface AssetSelectorProps {
  onSelect: (symbol: string) => void;
  onClose: () => void;
  isOpen: boolean;
}

export const AssetSelector: React.FC<AssetSelectorProps> = ({
  onSelect,
  onClose,
  isOpen
}) => {
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<AssetRegistryItem['category'] | 'All'>('All');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    } else {
      setSearch('');
    }
  }, [isOpen]);

  const categories: ('All' | AssetRegistryItem['category'])[] = ['All', 'EQUITY', 'CRYPTO', 'ETF'];

  const filtered = ASSET_REGISTRY.filter(asset => {
    const matchesSearch = asset.symbol.toLowerCase().includes(search.toLowerCase()) ||
                          asset.name.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = activeCategory === 'All' || asset.category === activeCategory;
    return matchesSearch && matchesCategory;
  });

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case 'EQUITY': return <LineChart size={14} />;
      case 'CRYPTO': return <Coins size={14} />;
      case 'ETF': return <Globe size={14} />;
      default: return <Search size={14} />;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-950/40 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        className="w-full max-w-2xl bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col h-[550px]"
      >
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
              <Globe size={20} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">Asset Discovery</h3>
              <p className="text-xs text-slate-400">Select Institutional Equities or Crypto Pairs</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-800 rounded-lg text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Search Input */}
        <div className="p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
            <input
              ref={inputRef}
              type="text"
              placeholder="Search by ticker or company name (e.g. AAPL, Bitcoin...)"
              className="w-full bg-slate-950/50 border border-slate-800 rounded-xl py-3 pl-10 pr-4 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-700 transition-all"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        {/* Categories */}
        <div className="px-4 pb-4 flex gap-2 overflow-x-auto no-scrollbar">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider border transition-all flex items-center gap-2 whitespace-nowrap",
                activeCategory === cat
                  ? "bg-slate-100 border-slate-100 text-slate-900"
                  : "bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-300"
              )}
            >
              {cat !== 'All' && getCategoryIcon(cat)}
              {cat}
            </button>
          ))}
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2 no-scrollbar">
          {filtered.length > 0 ? (
            filtered.map(asset => (
              <button
                key={asset.symbol}
                onClick={() => onSelect(asset.symbol)}
                className="w-full text-left p-4 rounded-xl border border-slate-800/50 hover:border-slate-700 hover:bg-slate-800/50 transition-all group relative overflow-hidden"
              >
                <div className="flex items-center justify-between relative z-10">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-400 group-hover:text-cyan-400 transition-colors">
                      {getCategoryIcon(asset.category)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-200">{asset.symbol}</span>
                        <span className="text-[9px] font-bold text-slate-500 px-1.5 py-0.5 rounded bg-slate-950 border border-slate-800 uppercase tracking-tighter">{asset.exchange}</span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">{asset.name}</p>
                    </div>
                  </div>
                  <Plus size={16} className="text-slate-600 group-hover:text-slate-300 opacity-0 group-hover:opacity-100 transition-all" />
                </div>
                <div className="absolute inset-0 opacity-0 group-hover:opacity-5 transition-opacity bg-cyan-500" />
              </button>
            ))
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 py-10 opacity-50">
              <Search size={40} className="mb-4" />
              <p className="text-sm">No assets found for "{search}"</p>
              <p className="text-xs mt-1">Try another ticker or search Equities/Crypto tabs.</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/50 text-[10px] text-slate-500 flex justify-between items-center">
          <p>ESC to Close • Click to Select</p>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="uppercase tracking-tighter font-bold text-[9px]">Market Feeds Active</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
};
