import { Archive, Edit2, MessageSquare, Trash2 } from "lucide-react";
import type { useTranslation } from "react-i18next";
import type { CommandPaletteRowAction } from "./CommandPaletteRowActions";

type Translate = ReturnType<typeof useTranslation>["t"];

/**
 * Row actions offered for one Omnisearch result. An owned conversation gets the
 * management set; a borrowed one can only be opened at its source.
 */
export function commandPaletteRowActions({
  item,
  t,
  navigationDisabled,
  onRename,
  onArchive,
  onDelete,
  onOpenSource,
}: {
  item: { canManageConversation?: boolean; conversationId?: string | null };
  t: Translate;
  navigationDisabled: boolean;
  onRename: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onOpenSource: () => void;
}): CommandPaletteRowAction[] {
  if (item.canManageConversation) {
    return [
      {
        id: "rename",
        label: t("command_palette.rename_conversation", "Rename conversation"),
        icon: Edit2,
        onSelect: onRename,
      },
      {
        id: "archive",
        label: t("command_palette.archive_conversation", "Archive conversation"),
        icon: Archive,
        onSelect: onArchive,
      },
      {
        id: "delete",
        label: t("command_palette.delete_conversation", "Delete conversation"),
        icon: Trash2,
        destructive: true,
        onSelect: onDelete,
      },
    ];
  }
  if (item.conversationId) {
    return [
      {
        id: "open_source",
        label: t(
          "command_palette.open_source_conversation",
          "Open source conversation",
        ),
        icon: MessageSquare,
        disabled: navigationDisabled,
        onSelect: onOpenSource,
      },
    ];
  }
  return [];
}
