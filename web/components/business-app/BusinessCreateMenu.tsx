"use client";

import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Tooltip } from "@/components/ui/Tooltip";
import type { ChatShellBridge } from "@/components/chat/ChatWorkspace";
import ActionMenu from "./ActionMenu";
import { useBusiness } from "./BusinessWorkspace";

/** + Create: at the sidebar foot on desktop, a header button on phones. */
export default function BusinessCreateMenu({
  shell,
  compact = false,
}: {
  shell: ChatShellBridge;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const { actions } = useBusiness();
  const label = t("business.create.label", "Create");

  if (compact) {
    return (
      <ActionMenu
        actions={actions.create}
        label={label}
        placement="below-end"
        renderTrigger={({ ref, open, toggle, menuId }) => (
          <button
            ref={ref}
            type="button"
            aria-label={label}
            aria-haspopup="menu"
            aria-expanded={open}
            aria-controls={open ? menuId : undefined}
            data-testid="business-create-compact"
            onClick={toggle}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-black text-white transition-opacity hover:opacity-85 focus-visible:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black/25 dark:bg-white dark:text-black"
          >
            <Plus className="h-5 w-5" />
          </button>
        )}
      />
    );
  }

  const collapsed = shell.sidebarCollapsed && !shell.isBelowTablet;
  return (
    <ActionMenu
      actions={actions.create}
      label={label}
      placement="above-start"
      portal={!shell.isBelowTablet}
      renderTrigger={({ ref, open, toggle, menuId }) => {
        const button = (
          <button
            ref={ref}
            type="button"
            aria-label={collapsed ? label : undefined}
            aria-haspopup="menu"
            aria-expanded={open}
            aria-controls={open ? menuId : undefined}
            data-testid="business-create"
            onClick={toggle}
            className={`flex h-11 items-center rounded-full bg-black text-white transition-opacity hover:opacity-85 focus-visible:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black/25 dark:bg-white dark:text-black ${
              collapsed ? "w-11 justify-center" : "w-full gap-2 px-4"
            }`}
          >
            <Plus className="h-5 w-5 shrink-0" />
            {collapsed ? null : (
              <span className="font-display text-[15px] font-medium tracking-tight">{label}</span>
            )}
          </button>
        );
        return collapsed ? (
          // The tooltip attaches its own ref to its child, so the button keeps
          // the menu's ref inside a wrapper.
          <Tooltip content={label} side="right" delay={150}>
            <span className="inline-flex">{button}</span>
          </Tooltip>
        ) : (
          button
        );
      }}
    />
  );
}
