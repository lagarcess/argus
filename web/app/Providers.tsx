"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, ReactNode } from "react";

import { getAuthSessionOptions } from "@/lib/api/@tanstack/react-query.gen";

export default function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => {
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 60 * 1000,
          refetchOnWindowFocus: false,
        },
      },
    });

    if (process.env.NEXT_PUBLIC_MOCK_AUTH === "true") {
      client.setQueryData(getAuthSessionOptions().queryKey, {
        id: "mock-dev-id",
        is_admin: true,
        subscription_tier: "max",
        backtest_quota: 100,
        remaining_quota: 100,
        feature_flags: { advanced_charting: true },
        theme: "dark",
      });
    }

    return client;
  });

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
