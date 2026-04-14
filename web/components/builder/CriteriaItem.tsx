'use client';

import React from 'react';
import { Trash2, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

export interface CriteriaItemData {
  indicator_a: string;
  operator: 'gt' | 'lt' | 'cross_above' | 'cross_below' | 'eq';
  indicator_b?: string;
  value?: number;
}

const OPERATORS = [
  { value: 'gt', label: 'is greater than' },
  { value: 'lt', label: 'is less than' },
  { value: 'cross_above', label: 'crosses above' },
  { value: 'cross_below', label: 'crosses below' },
  { value: 'eq', label: 'is equal to' },
];

interface CriteriaItemProps {
  item: CriteriaItemData;
  type: 'entry' | 'exit';
  canRemove: boolean;
  onRemove: () => void;
  onChange: (field: keyof CriteriaItemData, value: string | number | undefined) => void;
  onFocus: (field: 'indicator_a' | 'indicator_b') => void;
  onOpenSelector: (field: 'indicator_a' | 'indicator_b') => void;
}

export const CriteriaItem: React.FC<CriteriaItemProps> = ({
  item,
  type,
  canRemove,
  onRemove,
  onChange,
  onFocus,
  onOpenSelector
}) => {
  const themeColor = type === 'entry' ? 'text-blue-400' : 'text-rose-400';
  const themeGlow = type === 'entry' ? 'shadow-[0_0_10px_rgba(59,130,246,0.1)]' : 'shadow-[0_0_10px_rgba(244,63,94,0.1)]';

  const renderSlot = (field: 'indicator_a' | 'indicator_b', value: string | undefined) => {
    const isGhost = !value || value.trim() === '';
    const displayValue = isGhost ? 'Select Indicator' : value.split('_')[0];
    const param = !isGhost ? value.split('_')[1] : '';

    return (
      <div
        className={cn(
          "flex items-center h-8 rounded-full bg-slate-900 border border-slate-800 transition-all overflow-hidden shrink-0 group/slot cursor-pointer relative",
          isGhost ? "border-dashed opacity-80 hover:opacity-100" : "border-solid",
          isGhost && (type === 'entry' ? "hover:border-blue-500/50 hover:ring-1 hover:ring-blue-500/20" : "hover:border-rose-500/50 hover:ring-1 hover:ring-rose-500/20")
        )}
        onClick={() => {
          onFocus(field);
          onOpenSelector(field);
        }}
      >
        <button
          type="button"
          className={cn(
            "h-full px-3 text-[11px] font-bold transition-colors flex items-center gap-2",
            isGhost ? "text-slate-500 italic" : "text-slate-200"
          )}
        >
          {isGhost && <Search size={10} className="text-slate-600" />}
          {displayValue}
        </button>

        {!isGhost && (
          <div className="flex items-center px-2 gap-1 h-full bg-slate-950/40 border-l border-slate-800" onClick={(e) => e.stopPropagation()}>
            <input
              type="number"
              value={param}
              onChange={(e) => {
                const newInd = `${displayValue}_${e.target.value}`;
                onChange(field, newInd);
              }}
              onFocus={() => onFocus(field)}
              className={cn("w-8 bg-transparent text-[11px] font-mono focus:outline-none text-center", themeColor)}
            />
          </div>
        )}

        {isGhost && (
          <motion.div
            animate={{ opacity: [0.4, 0.8, 0.4] }}
            transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
            className={cn(
              "absolute inset-0 pointer-events-none",
              type === 'entry' ? "bg-blue-500/20" : "bg-rose-500/20"
            )}
          />
        )}
      </div>
    );
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="relative group flex items-center gap-2"
    >
      <div className={cn(
        "flex-1 flex flex-wrap items-center gap-2 p-1.5 rounded-2xl bg-slate-950/50 border border-slate-800/30 transition-all group-hover:bg-slate-900/40",
        themeGlow,
        type === 'entry' ? "hover:border-blue-500/20" : "hover:border-rose-500/20"
      )}>

        {/* Indicator A */}
        {renderSlot('indicator_a', item.indicator_a)}

        {/* Operator */}
        <div className="px-1">
          <select
            value={item.operator}
            onChange={(e) => onChange("operator", e.target.value)}
            className={cn(
              "bg-transparent text-[11px] font-medium text-slate-400 transition-colors focus:outline-none appearance-none cursor-pointer text-center px-1 border-b border-transparent hover:border-slate-700",
              `hover:${themeColor}`
            )}
          >
            {OPERATORS.map(op => <option key={op.value} value={op.value} className="bg-slate-950">{op.label}</option>)}
          </select>
        </div>

        {/* Target Switcher + Slot B / Value */}
        <div className="flex items-center gap-2">
           <select
            value={item.indicator_b ? "indicator" : "value"}
            onChange={(e) => {
              if (e.target.value === "value") {
                onChange("indicator_b", undefined);
                onChange("value", 50);
              } else {
                onChange("indicator_b", ""); // Trigger Ghost Slot
                onChange("value", undefined);
                onFocus('indicator_b');
                onOpenSelector('indicator_b');
              }
            }}
            className={cn(
              "bg-slate-900/50 border border-slate-800 px-2 py-1 rounded-lg text-[9px] text-slate-500 uppercase font-bold focus:outline-none appearance-none cursor-pointer hover:bg-slate-800 transition-colors"
            )}
          >
            <option value="value" className="bg-slate-950">Level</option>
            <option value="indicator" className="bg-slate-950">Indicator</option>
          </select>

          {item.indicator_b !== undefined ? (
            renderSlot('indicator_b', item.indicator_b)
          ) : (
            <div className={cn(
              "flex items-center h-8 px-4 rounded-full bg-slate-900 border border-slate-800 transition-all focus-within:ring-1 focus-within:ring-emerald-500/30"
            )}>
              <input
                type="number"
                value={item.value !== undefined ? item.value : 50}
                onChange={(e) => onChange("value", parseFloat(e.target.value))}
                className="w-12 bg-transparent text-[11px] text-emerald-400 font-mono focus:outline-none text-center"
              />
            </div>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={onRemove}
        disabled={!canRemove}
        className={cn(
          "w-8 h-8 flex items-center justify-center rounded-full transition-all shrink-0",
          !canRemove
            ? "text-slate-800 opacity-10 cursor-not-allowed"
            : "text-slate-600 hover:text-red-400 hover:bg-red-400/5 opacity-0 group-hover:opacity-100"
        )}
      >
        <Trash2 size={12} />
      </button>
    </motion.div>
  );
};
