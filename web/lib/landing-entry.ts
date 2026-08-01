export type LandingAuthMode = "intro" | "request" | "signup" | "login";

export type LandingEntrySurface = "loading" | "guest" | "auth";

export function resolveLandingEntrySurface(input: {
  authMode: LandingAuthMode;
  guestEntryAvailable: boolean;
  isCheckingSession: boolean;
}): LandingEntrySurface {
  if (input.isCheckingSession) return "loading";
  if (input.authMode !== "intro") return "auth";
  return input.guestEntryAvailable ? "guest" : "auth";
}
