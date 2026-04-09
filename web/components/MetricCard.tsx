"use client";

interface MetricCardProps {
  value: string;
  label: string;
  className?: string;
}

export function MetricCard({ value, label, className = "" }: MetricCardProps) {
  return (
    <div className={className}>
      <div className="text-3xl font-headline font-black text-on-surface">{value}</div>
      <div className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">
        {label}
      </div>
    </div>
  );
}
