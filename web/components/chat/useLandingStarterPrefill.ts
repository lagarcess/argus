"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  captureLandingIntentFromLocation,
  LANDING_STARTER_COPY_FALLBACKS,
  landingStarterCopyKey,
  takeLandingStarterPrefill,
  type LandingStarter,
} from "@/lib/landing-intent";

export function useLandingStarterPrefill(): string | null {
  const { t } = useTranslation();
  const [starter, setStarter] = useState<LandingStarter | null>(null);

  useEffect(() => {
    captureLandingIntentFromLocation();
    setStarter(takeLandingStarterPrefill());
  }, []);

  if (!starter) return null;
  return t(landingStarterCopyKey(starter), LANDING_STARTER_COPY_FALLBACKS[starter]);
}
