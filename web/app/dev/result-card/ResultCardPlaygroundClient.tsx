"use client";

import { useEffect } from "react";
import StrategyResultCard from "@/components/chat/StrategyResultCard";
import { resultCardPlaygroundFixtures } from "@/lib/result-card-playground-fixtures";

const appearanceFrames = [
  {
    id: "light",
    label: "Light",
    className: "bg-[#f4f5f2] text-black",
    innerClassName: "border-[#c9c9cd]/70 bg-white",
  },
  {
    id: "dark",
    label: "Dark",
    className: "dark bg-[#141517] text-white",
    innerClassName: "border-white/10 bg-white/[0.03]",
  },
];

export default function ResultCardPlaygroundClient() {
  useEffect(() => {
    const root = document.documentElement;
    const hadDarkClass = root.classList.contains("dark");
    root.classList.remove("dark");

    return () => {
      if (hadDarkClass) {
        root.classList.add("dark");
      }
    };
  }, []);

  return (
    <main className="min-h-screen bg-[#eef0ed] px-4 py-6 text-black dark:bg-[#101113] dark:text-white sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
        <header className="flex flex-col gap-2">
          <p className="text-[12px] font-medium tracking-[0.16px] text-[#8d969e]">
            Dev only
          </p>
          <h1 className="font-display text-[32px] font-medium tracking-[-0.32px] sm:text-[42px]">
            Hero + Delta Evidence Card
          </h1>
          <p className="max-w-2xl text-[14px] leading-6 tracking-[0.16px] text-[#505a63] dark:text-[#8d969e]">
            Static fixtures only. No auth, no API calls, no market data, no persistence.
          </p>
        </header>

        <div className="grid gap-6 xl:grid-cols-2">
          {appearanceFrames.map((frame) => (
            <section
              key={frame.id}
              className={`${frame.className} rounded-[22px] border border-[#c9c9cd]/70 p-4 dark:border-white/10 sm:p-5`}
              aria-label={`${frame.label} result card previews`}
            >
              <div className={`mb-4 rounded-[14px] border px-3 py-2 ${frame.innerClassName}`}>
                <h2 className="text-[15px] font-medium tracking-[0.16px]">{frame.label}</h2>
              </div>
              <div className="grid gap-5">
                {resultCardPlaygroundFixtures.map((fixture) => (
                  <PreviewCard key={`${frame.id}-${fixture.id}`} fixtureId={fixture.id}>
                    <PreviewHeader name={fixture.name} note={fixture.note} />
                    <StrategyResultCard
                      appearance={frame.id === "dark" ? "dark" : "light"}
                      result={fixture.result}
                    />
                  </PreviewCard>
                ))}
              </div>
            </section>
          ))}
        </div>

        <section
          className="rounded-[22px] border border-[#c9c9cd]/70 bg-[#f4f5f2] p-4 dark:border-white/10 dark:bg-[#141517] sm:p-5"
          aria-label="Mobile width result card previews"
        >
          <div className="mb-4 flex flex-col gap-1">
            <h2 className="text-[15px] font-medium tracking-[0.16px]">Mobile width</h2>
            <p className="text-[12px] leading-5 tracking-[0.16px] text-[#8d969e]">
              The frame below is capped at 390px for narrow viewport checks.
            </p>
          </div>
          <div className="mx-auto grid w-full max-w-[390px] gap-5">
            {resultCardPlaygroundFixtures.map((fixture) => (
              <PreviewCard key={`mobile-${fixture.id}`} fixtureId={fixture.id}>
                <PreviewHeader name={fixture.name} note={fixture.note} />
                <StrategyResultCard result={fixture.result} />
              </PreviewCard>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

function PreviewCard({
  children,
  fixtureId,
}: {
  children: React.ReactNode;
  fixtureId: string;
}) {
  return (
    <article
      data-testid={`result-card-fixture-${fixtureId}`}
      className="rounded-[18px] border border-[#c9c9cd]/50 bg-transparent p-3 dark:border-white/8"
    >
      {children}
    </article>
  );
}

function PreviewHeader({ name, note }: { name: string; note: string }) {
  return (
    <div className="mb-3 flex flex-col gap-1 px-1">
      <h3 className="text-[13px] font-medium leading-snug tracking-[0.16px] text-[#191c1f] dark:text-white">
        {name}
      </h3>
      <p className="text-[12px] leading-snug tracking-[0.16px] text-[#8d969e]">
        {note}
      </p>
    </div>
  );
}
