import type { Metadata } from "next";

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
    <div className="flex min-h-full w-full flex-col bg-[#191c1f]">
      {children}
    </div>
  );
}
