import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: [new URL("./overlay-history.ts", import.meta.url).pathname],
  bundle: true,
  write: false,
  platform: "node",
  format: "esm",
});
const {
  navigateAfterOverlays,
  overlayHistoryState,
  recordOverlayEntry,
  resetOverlayEntries,
} = await import(
  `data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].text).toString("base64")}`
);

const originalWindow = globalThis.window;
afterEach(() => {
  resetOverlayEntries();
  globalThis.window = originalWindow;
});

function browserHistory() {
  const browser = new EventTarget();
  const entries = [{ state: null, hash: "#overview" }];
  let cursor = 0;
  const history = {
    get state() {
      return entries[cursor].state;
    },
    pushState(state, _title, hash) {
      entries.splice(cursor + 1);
      entries.push({ state, hash });
      cursor++;
    },
    go(delta) {
      queueMicrotask(() => {
        cursor += delta;
        browser.dispatchEvent(new Event("popstate"));
      });
    },
    back() {
      this.go(-1);
    },
  };
  Object.assign(browser, {
    history,
    location: {
      get hash() {
        return entries[cursor].hash;
      },
    },
  });
  globalThis.window = browser;
  return { entries, history, current: () => entries[cursor].hash };
}

for (const depth of [0, 1, 2, 3, 5])
  test(`navigation removes ${depth} temporary overlay steps in both directions`, async () => {
    const browser = browserHistory();
    for (let index = 0; index < depth; index++) {
      const id = `modal-${index}`;
      recordOverlayEntry(id);
      browser.history.pushState(
        overlayHistoryState(browser.history.state, id),
        "",
        "#overview",
      );
    }
    navigateAfterOverlays(() =>
      browser.history.pushState(null, "", "#settings"),
    );
    await Promise.resolve();
    assert.deepEqual(
      browser.entries.map((entry) => entry.hash),
      ["#overview", "#settings"],
    );
    browser.history.back();
    await Promise.resolve();
    assert.equal(browser.current(), "#overview");
    browser.history.go(1);
    await Promise.resolve();
    assert.equal(browser.current(), "#settings");
  });

test("latest destination wins if navigation changes during overlay consumption", async () => {
  const browser = browserHistory();
  recordOverlayEntry("modal");
  browser.history.pushState(
    overlayHistoryState(null, "modal"),
    "",
    "#overview",
  );
  navigateAfterOverlays(() => browser.history.pushState(null, "", "#settings"));
  navigateAfterOverlays(() => browser.history.pushState(null, "", "#accounts"));
  await Promise.resolve();
  assert.deepEqual(
    browser.entries.map((entry) => entry.hash),
    ["#overview", "#accounts"],
  );
});
