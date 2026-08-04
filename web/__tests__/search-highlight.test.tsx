import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import { SearchHighlight } from "../components/sidebar/SearchHighlight";

function markedText(html: string): string[] {
  return Array.from(
    html.matchAll(/<mark[^>]*>(.*?)<\/mark>/g),
    ([, text]) => text,
  );
}

describe("Omnisearch matched-context highlighting", () => {
  test("highlights separated normalized query tokens", () => {
    const html = renderToStaticMarkup(
      <SearchHighlight
        text="Copper lantern threshold"
        query="copper threshold"
      />,
    );

    expect(markedText(html)).toEqual(["Copper", "threshold"]);
    expect(html.replace(/<[^>]+>/g, "")).toBe("Copper lantern threshold");
  });

  test("preserves display punctuation and casefold-equivalent text", () => {
    const html = renderToStaticMarkup(
      <SearchHighlight text="Straße—Threshold" query="STRASSE, threshold" />,
    );

    expect(markedText(html)).toEqual(["Straße", "Threshold"]);
    expect(html.replace(/<[^>]+>/g, "")).toBe("Straße—Threshold");
  });

  test("highlights backend-valid I matches in a Turkish-locale browser", () => {
    const localeLowerCase = String.prototype.toLocaleLowerCase;
    String.prototype.toLocaleLowerCase = function () {
      return localeLowerCase.call(this, "tr");
    };

    try {
      const html = renderToStaticMarkup(
        <SearchHighlight text="Idea threshold" query="i threshold" />,
      );

      expect(markedText(html)).toEqual(["Idea", "threshold"]);
      expect(html.replace(/<[^>]+>/g, "")).toBe("Idea threshold");
    } finally {
      String.prototype.toLocaleLowerCase = localeLowerCase;
    }
  });

  test("highlights pinned Unicode 13 scalars without browser property tables", () => {
    const yezidiElif = "𐺀";
    const stringMatchAll = String.prototype.matchAll;
    String.prototype.matchAll = function (regexp: RegExp) {
      const matches = stringMatchAll.call(this, regexp);
      if (regexp.source !== "[\\p{L}\\p{N}]+") return matches;
      return (function* () {
        for (const match of matches) {
          if (!match[0].includes(yezidiElif)) yield match;
        }
      })();
    };

    let html: string;
    try {
      html = renderToStaticMarkup(
        <SearchHighlight
          text={`${yezidiElif} Straße threshold`}
          query={`${yezidiElif} ss threshold`}
        />,
      );
    } finally {
      String.prototype.matchAll = stringMatchAll;
    }

    expect(markedText(html)).toEqual([yezidiElif, "Straße", "threshold"]);
    expect(html.replace(/<[^>]+>/g, "")).toBe(
      `${yezidiElif} Straße threshold`,
    );
  });
});
