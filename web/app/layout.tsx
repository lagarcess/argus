import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { I18nProvider } from "@/components/I18nProvider";
import localFont from "next/font/local";

const inter = localFont({
  src: "./fonts/InterVariable.woff2",
  variable: "--font-inter",
  weight: "100 900",
});

const spaceGrotesk = localFont({
  src: "./fonts/SpaceGrotesk[wght].woff2",
  variable: "--font-space-grotesk",
  weight: "300 700",
});

export const metadata: Metadata = {
  title: "Argus",
  description: "Next Generation Platform",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#191c1f",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="antialiased h-full">
      <body className={`${spaceGrotesk.variable} ${inter.variable} min-h-full flex flex-col font-sans transition-colors duration-200`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          storageKey="argus-theme"
          enableSystem
          disableTransitionOnChange
        >
          <I18nProvider>
            {children}
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
