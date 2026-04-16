export function resolveOnboardingRedirect(params: {
  onboardingCompleted?: boolean;
  pathname: string;
  search?: string;
}): string | null {
  const { onboardingCompleted, pathname, search = "" } = params;

  if (onboardingCompleted === undefined) return null;

  if (!onboardingCompleted && pathname !== "/onboarding") {
    return "/onboarding";
  }

  if (onboardingCompleted && pathname === "/onboarding") {
    return `/builder${search}`;
  }

  return null;
}
