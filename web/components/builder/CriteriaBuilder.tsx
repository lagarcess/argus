'use client';

import React from 'react';
import { Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CriteriaItem, CriteriaItemData } from './CriteriaItem';

interface CriteriaBuilderProps {
  label: string;
  items: CriteriaItemData[];
  type: 'entry' | 'exit';
  onAdd: () => void;
  onRemove: (idx: number) => void;
  onChange: (idx: number, field: keyof CriteriaItemData, value: any) => void;
  onFocus: (idx: number, field: 'indicator_a' | 'indicator_b') => void;
  onOpenSelector: (idx: number, field: 'indicator_a' | 'indicator_b') => void;
}

export const CriteriaBuilder: React.FC<CriteriaBuilderProps> = ({
  label,
  items,
  type,
  onAdd,
  onRemove,
  onChange,
  onFocus,
  onOpenSelector
}) => {
  const canAddRule = items.length < 1 || process.env.NEXT_PUBLIC_FEATURE_MULTI_RULES === "true";
  const themeColor = type === 'entry' ? 'text-blue-400' : 'text-rose-400';
  const themeBg = type === 'entry' ? 'bg-blue-500/5' : 'bg-rose-500/5';
  const themeBorder = type === 'entry' ? 'border-blue-500/10' : 'border-rose-500/10';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
           <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">{label}</h3>
           <div className={cn("px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[8px] font-bold uppercase", themeColor)}>
              {items.length} {items.length === 1 ? 'Rule' : 'Rules'}
           </div>
        </div>
        {canAddRule && (
          <button
            type="button"
            onClick={onAdd}
            className={cn(
              "group flex items-center gap-1.5 px-3 py-1 rounded-full transition-all border",
              themeBg, themeBorder, "hover:bg-opacity-20"
            )}
          >
            <Plus size={10} className={themeColor} />
            <span className={cn("text-[10px] font-bold uppercase tracking-widest", themeColor)}>Add Rule</span>
          </button>
        )}
      </div>

      <div className="space-y-2">
        {items.map((item, idx) => (
          <CriteriaItem
            key={`${idx}-${item.indicator_a}-${item.indicator_b}`}
            idx={idx}
            item={item}
            type={type}
            canRemove={items.length > 1}
            onRemove={() => onRemove(idx)}
            onChange={(field, value) => onChange(idx, field, value)}
            onFocus={(field) => onFocus(idx, field)}
            onOpenSelector={(field) => onOpenSelector(idx, field)}
          />
        ))}
      </div>
    </div>
  );
};
