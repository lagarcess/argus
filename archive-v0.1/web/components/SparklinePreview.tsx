"use client";

import { useMemo, useEffect, useState } from "react";
import { LineChart, Line, ResponsiveContainer } from "recharts";

// Very naive mock data generator to instantly show the "shape" of an asset's data
// so we don't have to wait for an API call just for a decorative preview.
function generateMockSparkline(asset: string, seed: number) {
  const data = [];
  let price = 100 + (seed * 10);
  let volatility = 0.02 + (seed * 0.01);

  // If it's a stablecoin/tether, make it flat. If BTC, make it wilder.
  if (asset.includes("USDT") && asset.length <= 4) volatility = 0.001;
  if (asset.includes("BTC")) volatility = 0.05;

  for (let i = 0; i < 50; i++) {
    // Random walk with drift
    const change = price * volatility * (Math.random() - 0.45);
    price += change;
    data.push({ i, val: price });
  }
  return data;
}

export function SparklinePreview({ assetName }: { assetName: string }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const data = useMemo(() => {
    // Generate deterministic-ish data based on string length and first char code
    const seed = assetName ? (assetName.length + (assetName.charCodeAt(0) || 0)) % 10 : 1;
    return generateMockSparkline(assetName, seed);
  }, [assetName]);

  if (!mounted || !assetName) return null;

  return (
    <div className="absolute inset-0 pointer-events-none opacity-20 -z-10 overflow-hidden rounded-xl">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="val"
            stroke="#99f7ff"
            strokeWidth={2}
            dot={false}
            isAnimationActive={true}
            animationDuration={2000}
            animationEasing="ease-in-out"
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Gradient mask to fade out edges */}
      <div className="absolute inset-0 bg-gradient-to-t from-surface-container-low via-transparent to-surface-container-low pointer-events-none" />
      <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-surface-container-low to-transparent pointer-events-none" />
    </div>
  );
}
