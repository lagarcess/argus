"use client";

import { useState } from "react";
import ChatInterface from "@/components/chat/ChatInterface";
import { BusinessWorkspaceProvider } from "./BusinessWorkspace";
import { liveBusinessDataSource, type BusinessDataSource } from "./business-data";
import { createFixtureBusinessDataSource } from "./fixture-data";

export default function BusinessApp({ sampleData = false }: { sampleData?: boolean }) {
  const [source] = useState<BusinessDataSource>(() =>
    sampleData ? createFixtureBusinessDataSource() : liveBusinessDataSource,
  );
  return (
    <BusinessWorkspaceProvider source={source}>
      <ChatInterface />
    </BusinessWorkspaceProvider>
  );
}
