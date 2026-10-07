"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import ChatInput from "./ChatInput";
import type {
  ChatShellBridge,
  ChatShellView,
  ChatWorkspace,
} from "./ChatWorkspace";
import type { ChatMention } from "./types";

type ShellBridgeInput = {
  workspace: ChatWorkspace | null;
  currentView: ChatShellView;
  conversationId: string | null;
  isBelowTablet: boolean;
  sidebarCollapsed: boolean;
  setCurrentView: (view: ChatShellView) => void;
  resetToEmptyChatSurface: () => void;
  closeTransientSidebar: () => void;
};

export type ShellBridgeWithSlots = {
  bridge: ChatShellBridge;
  profileSlot: HTMLElement | null;
  setProfileSlot: (element: HTMLElement | null) => void;
};

export function useChatShellBridge({
  workspace,
  currentView,
  conversationId,
  isBelowTablet,
  sidebarCollapsed,
  setCurrentView,
  resetToEmptyChatSurface,
  closeTransientSidebar,
}: ShellBridgeInput): ShellBridgeWithSlots {
  const [profileSlot, setProfileSlot] = useState<HTMLElement | null>(null);
  const [preparedQuestion, setPreparedQuestion] = useState<string | null>(null);
  const bridge = useMemo<ChatShellBridge>(
    () => ({
      currentView,
      conversationId,
      isBelowTablet,
      sidebarCollapsed,
      showWorkspace: () => {
        resetToEmptyChatSurface();
        setCurrentView("workspace");
        closeTransientSidebar();
      },
      newChat: () => {
        resetToEmptyChatSurface();
        setCurrentView("chat");
        closeTransientSidebar();
      },
      prepareQuestion: (text: string) => {
        resetToEmptyChatSurface();
        setCurrentView("chat");
        setPreparedQuestion(text);
        closeTransientSidebar();
      },
    }),
    [
      closeTransientSidebar,
      conversationId,
      currentView,
      isBelowTablet,
      resetToEmptyChatSurface,
      setCurrentView,
      sidebarCollapsed,
    ],
  );
  useEffect(() => {
    workspace?.onShellChange(bridge);
  }, [bridge, workspace]);
  useEffect(() => {
    if (preparedQuestion === null || !workspace) return;
    workspace.composer(bridge).replaceDraft(preparedQuestion);
    setPreparedQuestion(null);
  }, [bridge, preparedQuestion, workspace]);
  return { bridge, profileSlot, setProfileSlot };
}

export function workspaceComposerProps(
  workspace: ChatWorkspace | null,
  bridge: ChatShellBridge,
) {
  if (!workspace) return {};
  const { leadingControl, draftText, onDraftChange, placeholder } = workspace.composer(bridge);
  return { leadingControl, draftText, onDraftChange, placeholder };
}

type WorkspaceMainProps = {
  workspace: ChatWorkspace;
  bridge: ChatShellBridge;
  composerNotice?: ReactNode;
  disabled: boolean;
  onToast: (message: string) => void;
  onSend: (
    text: string,
    mentions?: ChatMention[],
  ) => void | boolean | Promise<void | boolean>;
};

/** The main area while a workspace panel is showing, composer included. */
export function WorkspaceMain({
  workspace,
  bridge,
  composerNotice,
  disabled,
  onToast,
  onSend,
}: WorkspaceMainProps) {
  const composer = workspace.composer(bridge);
  return (
    <div className="relative mx-auto flex h-[100dvh] w-full max-w-5xl flex-col">
      <div
        data-testid="workspace-panel-region"
        className="argus-scrollbar flex-1 overflow-y-auto px-4 pt-[86px] tablet:px-8"
        style={{ paddingBottom: workspace.panelHasComposer ? 190 : 48 }}
      >
        {workspace.panel(bridge)}
      </div>
      {workspace.panelHasComposer ? (
        <>
          <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-40 bg-[#f9f9f9]/80 backdrop-blur-[0.8px] [mask-image:linear-gradient(to_top,black_50%,transparent_100%)] dark:bg-[#141517]/80" />
          <div className="pointer-events-none absolute inset-x-0 bottom-6 z-20 px-4">
            <div className="pointer-events-auto mx-auto max-w-3xl">
              {composerNotice}
              <ChatInput
                key={composer.draftKey}
                onSend={onSend}
                disabled={disabled}
                placeholder={composer.placeholder}
                onToast={onToast}
                leadingControl={composer.leadingControl}
                draftText={composer.draftText}
                onDraftChange={composer.onDraftChange}
              />
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
