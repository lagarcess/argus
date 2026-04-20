import { SettingsMenu } from "@/components/SettingsMenu";

export default function LandingPage() {
  return (
    <main className="relative flex min-h-[100dvh] w-full flex-col justify-between overflow-hidden px-6 py-8 md:px-12">
      <SettingsMenu />
      {/* 
        We have removed the glowing Card Bezel entirely.
        This provides the edge-to-edge minimalist aesthetic seen in Grok and Revolut.
      */}

      {/* Logo Section */}
      <div className="flex flex-grow items-center justify-center">
        {/* Space Grotesk tightly tracked per the typography rules */}
        <h1 className="text-6xl md:text-[80px] font-medium tracking-tight text-black dark:text-white z-10 select-none transition-colors">
          argus
        </h1>
      </div>
      
      {/* Subtle Curve SVG Background Graphic - Toggled Off */}
      {process.env.NEXT_PUBLIC_SHOW_BACKGROUND_CURVE === 'true' && (
        <div className="pointer-events-none absolute left-0 top-[46%] md:top-[53%] flex -translate-y-1/2 w-full justify-center z-0 overflow-hidden h-[150px]">
          <svg
            fill="none"
            height="100%"
            preserveAspectRatio="xMidYMid slice"
            viewBox="0 0 300 100"
            width="100%"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M0 60 Q 150 0 300 60"
              stroke="currentColor"
              className="text-black/10 dark:text-white/20 transition-colors"
              strokeWidth="0.55"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        </div>
      )}

      {/* Bottom Action Section */}
      {/* Normalized font sizes and button padding per DESIGN.md */}
      <div className="relative z-10 flex w-full flex-col items-center gap-6 pb-2 md:pb-4">
        <button className="w-full max-w-sm rounded-[9999px] bg-black text-white dark:bg-white dark:text-black px-[32px] py-[14px] text-[16px] font-medium transition-opacity hover:opacity-85 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:focus-visible:ring-white">
          Sign up with Email
        </button>
        <p className="text-[16px] tracking-wide text-gray-500 dark:text-gray-400">
          already have an account?{" "}
          <a
            className="font-medium text-black dark:text-white transition-opacity hover:opacity-80"
            href="#"
          >
            sign in
          </a>
        </p>

        {/* Legal Footer */}
        <p className="mt-4 w-full px-4 text-center text-[11px] md:text-[12px] text-zinc-500 tracking-tight">
          By signing up, you agree to our{" "}
          <a href="#" className="font-semibold text-zinc-800 dark:text-zinc-400 hover:text-black dark:hover:text-white transition-colors">
            Terms
          </a>{" "}
          and{" "}
          <a href="#" className="font-semibold text-zinc-800 dark:text-zinc-400 hover:text-black dark:hover:text-white transition-colors">
            Privacy Policy
          </a>.
        </p>
      </div>
    </main>
  );
}
