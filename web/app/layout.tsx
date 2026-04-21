import type { Metadata, Viewport } from "next";
import { Space_Grotesk } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
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
    <html lang="en" suppressHydrationWarning className={`${spaceGrotesk.variable} antialiased h-full`}>
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
