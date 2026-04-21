"use client";

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { client } from '@/lib/api/client.gen';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());

  // Configure the API client to point to our Prism mock server via env var
  client.setConfig({
    baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:4010',
  });

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
