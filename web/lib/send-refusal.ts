/** What the composer says when it declines a message.
 *
 * A refusal the person cannot see is worse than any wrong answer: they typed,
 * pressed send, and the app looked dead. Every path that declines a real
 * message reports through one of these. Two refusals are deliberately silent
 * because nothing was asked of Argus: empty input, and a send while one is
 * already in flight, where the composer is disabled anyway.
 *
 * `web/__tests__/guest-capability-gates.test.ts` holds that as an invariant
 * over the whole send handler, so a new silent refusal fails the suite rather
 * than reaching a stranger.
 */

/** Another turn already owns this conversation. Shared by the two paths that
 * mean it, so they cannot drift into two different sentences. */
export const SEND_BUSY_FALLBACK =
  "Argus is still finishing the last message. Try again in a moment.";

export const SEND_GENERIC_FALLBACK = "Something went wrong. Try again.";

/** Builds the composer's one refusal path: say it, then decline. */
export function sendRefusal(
  showToast: (message: string, variant: "error") => void,
  translate: (key: string, fallback: string) => string,
) {
  return (key: string, fallback: string) => {
    showToast(translate(key, fallback), "error");
    return false;
  };
}
