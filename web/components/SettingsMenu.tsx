"use client";

import GuestSettingsMenu from "@/components/guest/GuestSettingsMenu";

/** Auth screens share the guest browser preferences and responsive panels. */
export function SettingsMenu() {
  return (
    <div className="absolute right-6 top-6 z-40 text-[var(--color-argus-fg)] tablet:right-12 tablet:top-8">
      <GuestSettingsMenu feedbackEnabled={false} onFeedback={() => {}} />
    </div>
  );
}
