"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  captureLandingIntentFromLocation,
  LANDING_STARTER_COPY_FALLBACKS,
  landingStarterAppliedThisRuntime,
  landingStarterCopyKey,
  stripLandingStarterFromLocation,
  takeLandingStarterPrefill,
  type LandingStarter,
} from "@/lib/landing-intent";

export function useLandingStarterPrefill(): string | null {
  const { t } = useTranslation();
  const [starter, setStarter] = useState<LandingStarter | null>(null);

  useEffect(() => {
    captureLandingIntentFromLocation();
    const next =
      takeLandingStarterPrefill() ?? landingStarterAppliedThisRuntime();
    if (next) stripLandingStarterFromLocation();
    setStarter(next);
  }, []);

  if (!starter) return null;
  return t(landingStarterCopyKey(starter), LANDING_STARTER_COPY_FALLBACKS[starter]);
}
