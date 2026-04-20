import { Metadata, Viewport } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { AuthProvider } from "@/components/AuthContext";
import Providers from "./Providers";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "ARGUS | Argus Observatory",
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
      <body className="bg-slate-950 text-slate-100 font-body antialiased selection:bg-cyan-500/30 min-h-screen">
        <ThemeProvider defaultTheme="system">
          <AuthProvider>
            <Providers>
              {children}
              <Toaster position="top-right" theme="dark" richColors />
            </Providers>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
