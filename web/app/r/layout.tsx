import type { Metadata, Viewport } from "next";

/**
 * The public receipt shell. Deliberately not the app shell: no sidebar, no chat
 * chrome, no auth probe, no client i18n gate. A link opened from a messaging app
 * on a phone should paint once.
 *
 * One look, not two. A shared artifact is screenshotted and re-shared, so the
 * page and its preview card have to be the same object; honouring the viewer's
 * theme would make the link and the card that advertises it disagree.
 *
 * noindex lives here as well as in each page's metadata, so a future page added
 * under /r inherits it rather than having to remember it.
 */
export const viewport: Viewport = {
  // The action bar sits against the bottom edge, so it has to know how tall the iOS
  // home indicator is. env(safe-area-inset-*) reports zero unless the viewport opts
  // into the full screen, and this is set on the receipt route only: the app shell's
  // own viewport belongs to the responsive-shell lane.
  viewportFit: "cover",
};

export const metadata: Metadata = {
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: { index: false, follow: false, noimageindex: true },
  },
};

export default function PublicReceiptLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // Sized against the viewport, not against the parent. A percentage min-height
    // resolves against the containing block's height, and body sets min-height
    // without ever setting a height, so its own height stays content-based and the
    // percentage resolves to nothing. On any page shorter than the screen the dark
    // surface stopped at the last line and the white body showed underneath, which
    // on this route is a stranger's first sight of Argus.
    <div className="flex min-h-dvh w-full flex-col bg-[#191c1f]">
      {children}
    </div>
  );
}
