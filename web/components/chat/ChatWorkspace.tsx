"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { WorkspaceStarterEntry } from "./StarterActions";

/**
 * A workspace adds its own surfaces to the shared chat shell without copying
 * it. The shell keeps one owner for conversations, Recents, search, profile and
 * the composer; the workspace contributes navigation, panels and actions.
 *
 * `currentView === "workspace"` means a workspace panel fills the main area.
 * Which panel is the workspace's own fact, never the shell's.
 */
export type ChatShellView = "chat" | "settings" | "workspace";

export type ChatShellBridge = Readonly<{
  currentView: ChatShellView;
  conversationId: string | null;
  isBelowTablet: boolean;
  sidebarCollapsed: boolean;
  /** Shows the workspace's main panel, leaving any open conversation. */
  showWorkspace: () => void;
  /** Opens an empty conversation, like New chat. */
  newChat: () => void;
  /** Opens an empty conversation with editable text; never sends. */
  prepareQuestion: (text: string) => void;
}>;

export type WorkspaceComposer = Readonly<{
  leadingControl: ReactNode;
  placeholder: string;
  draftText: string | null;
  /** Changes only when the draft is replaced from outside the composer. */
  draftKey: string;
  onDraftChange: (text: string) => void;
  replaceDraft: (text: string) => void;
}>;

export type ChatWorkspace = Readonly<{
  id: string;
  initialView: ChatShellView;
  profileInHeader: boolean;
  /** Whether the current panel keeps the composer at its bottom edge. */
  panelHasComposer: boolean;
  sidebarNav: (bridge: ChatShellBridge) => ReactNode;
  sidebarFooter: (bridge: ChatShellBridge) => ReactNode;
  headerActions: (bridge: ChatShellBridge) => ReactNode;
  panel: (bridge: ChatShellBridge) => ReactNode;
  starterEntries: (bridge: ChatShellBridge) => readonly WorkspaceStarterEntry[];
  composer: (bridge: ChatShellBridge) => WorkspaceComposer;
  emptyChatLead: (bridge: ChatShellBridge) => ReactNode;
  onShellChange: (bridge: ChatShellBridge) => void;
}>;

const ChatWorkspaceContext = createContext<ChatWorkspace | null>(null);

export const ChatWorkspaceProvider = ChatWorkspaceContext.Provider;

export function useChatWorkspace(): ChatWorkspace | null {
  return useContext(ChatWorkspaceContext);
}
