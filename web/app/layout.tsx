import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";

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
      <body className="min-h-full flex flex-col font-sans transition-colors duration-200">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          storageKey="argus-theme"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
