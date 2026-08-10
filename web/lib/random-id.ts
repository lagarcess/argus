/** A v4 identifier that also works outside a secure context.
 *
 * `crypto.randomUUID` is defined only for secure origins, so it is present on
 * localhost and in production and absent when the app is served over plain
 * http from a LAN address, which is how the app gets opened on a phone during
 * device QA. Calling it there throws inside the send path and the screen goes
 * dead. `getRandomValues` is available either way, so the fallback carries the
 * same randomness and only does the formatting itself.
 */
export function randomId(): string {
  const source = globalThis.crypto;
  if (typeof source?.randomUUID === "function") {
    return source.randomUUID();
  }
  const bytes = new Uint8Array(16);
  source.getRandomValues(bytes);
  // Version 4, variant 1, exactly as randomUUID would set them.
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20),
  ].join("-");
}
