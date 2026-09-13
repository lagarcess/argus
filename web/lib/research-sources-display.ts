/**
 * Copy for a research turn's sources surface: the button under the answer
 * and the drawer it opens.
 *
 * A published answer's sources are sources. A degraded turn's sources are
 * the pages Argus read and could not verify the answer with, so the same
 * drawer is framed as where Argus looked, never as sources of an answer.
 * The framing is decided by the backend's typed degraded code carried on
 * the message; nothing here reads the pages or ranks them.
 */
export type ResearchSourcesDisplay = {
  openKey: string;
  openFallback: string;
  openFallbackOne: string;
  titleKey: string;
  titleFallback: string;
  noteKey: string;
  noteFallback: string;
};

export function researchSourcesDisplay(withheld: boolean): ResearchSourcesDisplay {
  if (withheld) {
    return {
      openKey: "chat.discovery_results.sources_panel_open_withheld",
      openFallback: "Where Argus looked ›",
      openFallbackOne: "Where Argus looked ›",
      titleKey: "chat.discovery_results.sources_panel_title_withheld",
      titleFallback: "Where Argus looked",
      noteKey: "chat.discovery_results.sources_panel_note_withheld",
      noteFallback:
        "Argus read these pages while answering and could not verify the answer with them. Links open in a new tab.",
    };
  }
  return {
    openKey: "chat.discovery_results.sources_panel_open",
    openFallback: "{{count}} sources ›",
    openFallbackOne: "{{count}} source ›",
    titleKey: "chat.discovery_results.sources_panel_title",
    titleFallback: "Sources Argus read",
    noteKey: "chat.discovery_results.sources_panel_note",
    noteFallback: "Argus read these while answering. Not recommended reading.",
  };
}
