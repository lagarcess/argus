import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";

export const metadata: Metadata = {
  title: "ARGUS | Obsidian Observatory",
  description: "Retail trading simulation SaaS. Backtest with reality gaps applied.",
  manifest: "/manifest.json",
  icons: {
    apple: "/icon-192x192.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#0e0e10",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-background text-on-surface font-body selection:bg-primary/30 min-h-screen">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
