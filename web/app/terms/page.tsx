import Link from "next/link";

const EFFECTIVE_DATE = "Effective date: June 30, 2026";
const SUPPORT_EMAIL =
  process.env.NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL ?? "support@argus.local";

export default function TermsPage() {
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
            href="/privacy"
            className="rounded-full border border-black/10 px-4 py-2 text-[13px] font-medium text-black/70 transition-colors hover:border-black/25 hover:text-black dark:border-white/15 dark:text-white/70 dark:hover:border-white/30 dark:hover:text-white"
          >
            Privacy Policy
          </Link>
        </header>

        <section className="pt-14 md:pt-20">
          <p className="mb-4 text-[12px] font-medium tracking-[0] text-black/45 dark:text-white/45">
            Private Alpha Legal
          </p>
          <h1 className="font-display max-w-[720px] text-[42px] font-medium leading-[1.05] tracking-[0] text-black dark:text-white md:text-[56px]">
            Terms of Use
          </h1>
          <p className="mt-4 text-[14px] font-medium text-black/45 dark:text-white/45">
            {EFFECTIVE_DATE}
          </p>
          <p className="mt-8 max-w-[680px] text-[17px] leading-8 text-black/65 dark:text-white/65">
            Argus is a private alpha product for educational investing research.
            These terms describe the current tester experience and do not
            replace final legal review.
          </p>
        </section>

        <div className="mt-12 space-y-10 border-t border-black/10 pt-10 dark:border-white/10">
          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              No investment advice
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Argus provides educational tools that help you structure and
              review investing ideas. Argus does not provide investment, legal,
              tax, accounting, or financial advice. You are responsible for your
              own decisions.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              No brokerage or trading relationship
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Argus is not a broker, dealer, investment adviser, fiduciary,
              exchange, custodian, or trading venue. Argus does not hold funds,
              place orders, execute trades, or connect to brokerage accounts.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Historical simulations are hypothetical
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Historical simulations are hypothetical and depend on the
              assumptions, data availability, asset support, benchmark defaults,
              and time windows shown in the product. Simulated returns are not
              guarantees of future performance.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Alpha availability and changes
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Argus is in private alpha. Features may change, break, reset, or
              be removed without notice. We may limit access, suspend accounts,
              or remove content that creates security, abuse, compliance, or
              operational risk.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Eligibility
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              You must be old enough to form a binding agreement in your
              jurisdiction and allowed to use Argus under applicable law. Do not
              use Argus on behalf of another person or organization unless you
              are authorized to do so.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Acceptable use
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Do not use Argus to break the law, abuse the service, reverse
              engineer private systems, overload providers, submit sensitive
              third-party data, or present generated output as professional
              advice.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Third-party services
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              Argus relies on third-party services for hosting, authentication,
              market data, model access, and chart rendering.{" "}
              {"TradingView Lightweight Charts"} is used for chart rendering
              and attribution, not as an Argus market data source.
            </p>
          </section>

          <section>
            <h2 className="font-display text-[24px] font-medium tracking-[0]">
              Account support
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
              During private alpha, account deletion and support requests are
              handled manually. Contact{" "}
              <a
                className="font-medium text-black underline decoration-black/25 underline-offset-4 transition-colors hover:decoration-black dark:text-white dark:decoration-white/30 dark:hover:decoration-white"
                href={`mailto:${SUPPORT_EMAIL}`}
              >
                {SUPPORT_EMAIL}
              </a>{" "}
              or use the in-app account deletion request.
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
