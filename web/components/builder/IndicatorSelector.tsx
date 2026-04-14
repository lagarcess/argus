'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Search, X, Star, TrendingUp, Activity, BarChart3, Zap, Plus } from 'lucide-react';
import { INDICATOR_REGISTRY, IndicatorMetadata } from '@/lib/indicators';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

interface IndicatorSelectorProps {
  type: 'entry' | 'exit';
  onSelect: (indicatorId: string) => void;
  onClose: () => void;
  isOpen: boolean;
}

export const IndicatorSelector: React.FC<IndicatorSelectorProps> = ({
  type,
  onSelect,
  onClose,
  isOpen
}) => {
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<IndicatorMetadata['category'] | 'All'>('All');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    } else {
      setSearch('');
    }
  }, [isOpen]);

  const categories = ['All', 'Trend', 'Momentum', 'Volatility', 'Volume'];

  const filtered = INDICATOR_REGISTRY.filter(ind => {
    const matchesSearch = ind.name.toLowerCase().includes(search.toLowerCase()) ||
                         ind.id.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = activeCategory === 'All' || ind.category === activeCategory;
    return matchesSearch && matchesCategory;
  });

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case 'Trend': return <TrendingUp size={14} />;
      case 'Momentum': return <Activity size={14} />;
      case 'Volatility': return <Zap size={14} />;
      case 'Volume': return <BarChart3 size={14} />;
      default: return <Star size={14} />;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/40 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="w-full max-w-2xl bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col h-[600px]"
      >
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className={cn(
              "p-2 rounded-lg",
              type === 'entry' ? "bg-blue-500/10 text-blue-400" : "bg-rose-500/10 text-rose-400"
            )}>
              <Search size={20} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">Indicator Library</h3>
              <p className="text-xs text-slate-400">Search 100+ Institutional Signal Sources</p>
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
              placeholder="Search by name or ticker (e.g. RSI, Bollinger...)"
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
              onClick={() => setActiveCategory(cat as IndicatorMetadata['category'] | 'All')}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium border transition-all flex items-center gap-2 whitespace-nowrap",
                activeCategory === cat
                  ? "bg-slate-100 border-slate-100 text-slate-900"
                  : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300"
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
            filtered.map(ind => (
              <button
                key={ind.id}
                onClick={() => onSelect(ind.id)}
                className="w-full text-left p-4 rounded-xl border border-slate-800/50 hover:border-slate-700 hover:bg-slate-800/50 transition-all group relative overflow-hidden"
              >
                <div className="flex items-center justify-between relative z-10">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-400 group-hover:text-slate-100 transition-colors">
                      {getCategoryIcon(ind.category)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-200">{ind.id}</span>
                        <span className="text-xs font-medium text-slate-500 px-1.5 py-0.5 rounded bg-slate-950 border border-slate-800">{ind.category}</span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">{ind.name}</p>
                    </div>
                  </div>
                  <Plus size={16} className="text-slate-600 group-hover:text-slate-300 opacity-0 group-hover:opacity-100 transition-all" />
                </div>
                <div className={cn(
                  "absolute inset-0 opacity-0 group-hover:opacity-5 transition-opacity",
                  type === 'entry' ? "bg-blue-500" : "bg-rose-500"
                )} />
              </button>
            ))
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 py-10 opacity-50">
              <Search size={40} className="mb-4" />
              <p className="text-sm">No indicators found for "{search}"</p>
              <p className="text-xs mt-1">Try searching by category or general term.</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/50 text-[10px] text-slate-500 flex justify-between items-center">
          <p>ESC to Close • Click to Snap</p>
        </div>
      </motion.div>
    </div>
  );
};
