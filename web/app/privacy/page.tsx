import Link from "next/link";

const EFFECTIVE_DATE = "Effective date: June 30, 2026";
const SUPPORT_EMAIL =
  process.env.NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL ?? "support@argus.local";

export default function PrivacyPage() {
  return (
    <main className="min-h-[100dvh] bg-white text-[#191c1f] dark:bg-[#191c1f] dark:text-white">
      <div className="mx-auto flex w-full max-w-3xl flex-col px-6 py-8 md:px-8 md:py-12">
        <header className="flex items-center justify-between gap-4 border-b border-black/10 pb-5 dark:border-white/10">
          <Link
            href="/"
            className="font-display text-[18px] font-medium tracking-[0] text-black dark:text-white"
          >
            argus
          </Link>
          <Link
            href="/terms"
            className="rounded-full border border-black/10 px-4 py-2 text-[13px] font-medium text-black/70 transition-colors hover:border-black/25 hover:text-black dark:border-white/15 dark:text-white/70 dark:hover:border-white/30 dark:hover:text-white"
          >
            Terms of Use
          </Link>
        </header>

        <section className="pt-14 md:pt-20">
          <p className="mb-4 text-[12px] font-medium tracking-[0] text-black/45 dark:text-white/45">
            Private Alpha Legal
          </p>
          <h1 className="font-display max-w-[720px] text-[42px] font-medium leading-[1.05] tracking-[0] text-black dark:text-white md:text-[56px]">
            Privacy Policy
          </h1>
          <p className="mt-4 text-[14px] font-medium text-black/45 dark:text-white/45">
            {EFFECTIVE_DATE}
          </p>
          <p className="mt-8 max-w-[680px] text-[17px] leading-8 text-black/65 dark:text-white/65">
            This policy explains what Argus handles during private alpha so
            testers know what happens to account data, conversations, feedback,
            and provider-backed requests.
          </p>
        </section>

        <div className="mt-12 space-y-10 border-t border-black/10 pt-10 dark:border-white/10">
          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Data we collect
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Argus may collect account details, authentication state,
              conversations, investing ideas you submit, saved product records,
              feedback, support requests, browser and device basics, usage
              events, logs, and error diagnostics.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              How we use data
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              We use data to run the product, authenticate users, save and
              restore conversations, generate and review historical simulations,
              debug failures, protect the service, respond to support, and
              improve private alpha quality.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              AI and market data providers
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Conversation content and prompts may be sent to OpenRouter and
              model providers so Argus can interpret requests and draft
              responses. Market data and asset discovery may use providers such
              as Alpaca and Kraken. Provider availability can affect supported
              symbols, time windows, and results.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Infrastructure and product services
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Argus uses Supabase for authentication and product persistence,
              Render for hosting, OpenRouter for model access, and PostHog only
              if product analytics are intentionally enabled.{" "}
              {"TradingView Lightweight Charts"} is used as a charting library
              with attribution; it is not the source of Argus market data.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Access and retention
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Founder and administrator access is limited to operating,
              debugging, securing, and improving the private alpha. We keep data
              while your account is active, while needed for support or security,
              or while required by operational records.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Your controls
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              You can archive or delete conversations in the app. During private
              alpha, account deletion is handled manually through the in-app
              request or by contacting{" "}
              <a
                className="font-medium text-black underline decoration-black/25 underline-offset-4 transition-colors hover:decoration-black dark:text-white dark:decoration-white/30 dark:hover:decoration-white"
                href={`mailto:${SUPPORT_EMAIL}`}
              >
                {SUPPORT_EMAIL}
              </a>
              .
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Sale of personal information
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Argus does not sell personal information during private alpha. If
              this changes, the policy and product controls must be updated
              before that behavior ships.
            </p>
          </section>
        </div>

        <footer className="mt-14 flex flex-col gap-3 border-t border-black/10 pt-6 text-[13px] text-black/45 dark:border-white/10 dark:text-white/45 sm:flex-row sm:items-center sm:justify-between">
          <span>Argus private alpha</span>
          <Link
            href="/"
            className="font-medium text-black/70 transition-colors hover:text-black dark:text-white/70 dark:hover:text-white"
          >
            Back to Argus
          </Link>
        </footer>
      </div>
    </main>
  );
}
