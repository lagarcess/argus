import test from "node:test";
import assert from "node:assert/strict";
import { build } from "esbuild";

async function loadModule(path) {
  const bundled = await build({
    entryPoints: [new URL(path, import.meta.url).pathname],
    bundle: true,
    write: false,
    platform: "node",
    format: "esm",
  });
  return import(
    `data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].text).toString("base64")}`
  );
}
const [composer, layout] = await Promise.all([
  loadModule("./composer-model.ts"),
  loadModule("./responsive-layout.ts"),
]);
const {
  composerMentions,
  serializeComposerSegments,
  replaceRangeWithToken,
  deleteTokenBeforeOffset,
  rawComposerText,
} = composer;
const { layoutForWidth, TABLET_MIN_WIDTH_PX, DESKTOP_MIN_WIDTH_PX } = layout;
const account = {
  id: "account-owned",
  type: "account",
  label: "Ahorro familiar",
  insert_text: "Ahorro familiar",
};

test("record references preserve exact normalized message ranges", () => {
  const segments = [
    { type: "text", text: "  ¿Qué queda en  " },
    { type: "token", token: account },
    { type: "text", text: "  este mes?  " },
  ];
  const text = serializeComposerSegments(segments);
  const mention = composerMentions(segments, text)[0];
  assert.equal(mention.id, account.id);
  assert.equal(mention.type, "account");
  assert.ok(mention.message_range);
  assert.equal(
    text.slice(mention.message_range.start, mention.message_range.end),
    account.insert_text,
  );
});

test("token insertion preserves surrounding text and deletion is atomic", () => {
  const next = replaceRangeWithToken(
    [{ type: "text", text: "Revisa @ahorro hoy" }],
    { start: 7, end: 14 },
    account,
  );
  assert.equal(rawComposerText(next), "Revisa Ahorro familiar hoy");
  const deleted = deleteTokenBeforeOffset(next, 7 + account.insert_text.length);
  assert.equal(rawComposerText(deleted.segments), "Revisa  hoy");
  assert.equal(deleted.offset, 7);
});

test("plain pasted record names never become trusted mentions", () => {
  assert.deepEqual(
    composerMentions([{ type: "text", text: account.insert_text }]),
    [],
  );
});

test("responsive layout uses canonical Argus thresholds", () => {
  assert.equal(layoutForWidth(TABLET_MIN_WIDTH_PX - 1).isBelowTablet, true);
  assert.equal(layoutForWidth(TABLET_MIN_WIDTH_PX).isBelowTablet, false);
  assert.equal(layoutForWidth(DESKTOP_MIN_WIDTH_PX - 1).isBelowDesktop, true);
  assert.equal(layoutForWidth(DESKTOP_MIN_WIDTH_PX).isBelowDesktop, false);
});
