"use client";

import { useTranslation } from "react-i18next";

import AppearanceModal from "@/components/settings/AppearanceModal";
import LanguageModal from "@/components/settings/LanguageModal";
import ArchivedChatsView from "@/components/settings/ArchivedChatsView";
import DeletedItemsView from "@/components/settings/DeletedItemsView";
import MemoryControlsModal from "@/components/settings/MemoryControlsModal";
import UsageModal from "@/components/settings/UsageModal";

/* Every settings surface the profile menu opens, registered once. A new panel
 * is an import and an entry: the key set is the type, and the menu derives its
 * ActiveModal union from it. The mobile-shell invariant enumerates the imports
 * above, so a panel cannot ship without a managed layer. */

export type SettingsPanelParent = "settings" | "data";

type SettingsPanelContext = {
  locale: "en-US" | "es-419";
  /** Where focus returns when a panel that took it closes. */
  anchorRef: React.RefObject<HTMLElement | null>;
  onClose: () => void;
  /** Only a sheet has a way back; above the panel line this is undefined. */
  onBack: (() => void) | undefined;
  backLabel: string;
  onHistoryMutated?: () => void;
};

type SettingsPanelEntry = {
  /** The submenu a sheet's back row returns to. */
  parent: SettingsPanelParent;
  render: (context: SettingsPanelContext) => React.ReactElement;
};

const SETTINGS_PANELS = {
  appearance: {
    parent: "settings",
    render: ({ onClose, onBack, backLabel }) => (
      <AppearanceModal onClose={onClose} onBack={onBack} backLabel={backLabel} />
    ),
  },
  language: {
    parent: "settings",
    render: ({ onClose, onBack, backLabel }) => (
      <LanguageModal onClose={onClose} onBack={onBack} backLabel={backLabel} />
    ),
  },
  archived: {
    parent: "data",
    render: ({ onClose, onBack, backLabel, onHistoryMutated }) => (
      <ArchivedChatsView
        onClose={onClose}
        onBack={onBack}
        backLabel={backLabel}
        onRestored={onHistoryMutated}
      />
    ),
  },
  deleted: {
    parent: "data",
    render: ({ onClose, onBack, backLabel, onHistoryMutated }) => (
      <DeletedItemsView
        onClose={onClose}
        onBack={onBack}
        backLabel={backLabel}
        onRestored={onHistoryMutated}
      />
    ),
  },
  usage: {
    parent: "data",
    render: ({ locale, onClose, onBack, backLabel, anchorRef }) => (
      <UsageModal
        locale={locale}
        onClose={onClose}
        onBack={onBack}
        backLabel={backLabel}
        returnFocusRef={anchorRef}
      />
    ),
  },
  memory: {
    parent: "data",
    render: ({ locale, onClose, onBack, backLabel, anchorRef }) => (
      <MemoryControlsModal
        locale={locale}
        onClose={onClose}
        onBack={onBack}
        backLabel={backLabel}
        returnFocusRef={anchorRef}
      />
    ),
  },
} satisfies Record<string, SettingsPanelEntry>;

export type SettingsPanel = keyof typeof SETTINGS_PANELS;

const PARENT_TITLE: Record<SettingsPanelParent, [string, string]> = {
  settings: ["settings.app.title", "Preferences"],
  data: ["settings.data.title", "Data Controls"],
};

type ProfileSettingsPanelsProps = {
  panel: SettingsPanel;
  /** Below the panel line a panel is a sheet, which is the only case with a way back. */
  asSheet: boolean;
  locale: "en-US" | "es-419";
  anchorRef: React.RefObject<HTMLElement | null>;
  onClose: () => void;
  onBack: (parent: SettingsPanelParent) => void;
  onHistoryMutated?: () => void;
};

export default function ProfileSettingsPanels({
  panel,
  asSheet,
  locale,
  anchorRef,
  onClose,
  onBack,
  onHistoryMutated,
}: ProfileSettingsPanelsProps) {
  const { t } = useTranslation();
  const { parent, render } = SETTINGS_PANELS[panel];
  const [titleKey, titleFallback] = PARENT_TITLE[parent];

  return render({
    locale,
    anchorRef,
    onClose,
    onBack: asSheet ? () => onBack(parent) : undefined,
    backLabel: t(titleKey, titleFallback),
    onHistoryMutated,
  });
}
