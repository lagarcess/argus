import type { ReactNode } from "react";

export type EntityTokenKind = "asset" | "indicator";
export type EntityTokenSurface = "composer" | "transcript" | "card";

export function entityTokenClassName(
  kind: EntityTokenKind,
  surface: EntityTokenSurface,
  focused = false,
) {
  const surfaceClass =
    surface === "card"
      ? "inline-flex select-none items-center rounded-[7px] border px-2 py-1 text-[12px] font-medium leading-none tracking-[0.16px]"
      : "mx-0.5 inline-flex max-w-40 select-none items-center rounded-[7px] border px-1.5 py-0.5 text-[1em] font-medium leading-[1.35] align-baseline";
  const kindClass =
    kind === "asset"
      ? "border-[#c9c9cd] bg-[#f7f7f8] text-[#505a63] dark:border-white/14 dark:bg-white/[0.04] dark:text-[#8d969e]"
      : "border-[#494fdf]/35 bg-[#494fdf]/[0.07] text-[#494fdf] dark:border-[#8f93ff]/45 dark:bg-[#8f93ff]/[0.12] dark:text-[#a9acff]";
  const composerFocusClass =
    surface === "composer"
      ? kind === "asset"
        ? "data-[entity-token-focused=true]:ring-1 data-[entity-token-focused=true]:ring-[#7c8791]/65 data-[entity-token-focused=true]:ring-offset-1 dark:data-[entity-token-focused=true]:ring-offset-[#191c1f]"
        : "data-[entity-token-focused=true]:ring-1 data-[entity-token-focused=true]:ring-[#494fdf]/60 data-[entity-token-focused=true]:ring-offset-1 dark:data-[entity-token-focused=true]:ring-offset-[#191c1f]"
      : "";
  const focusedClass =
    surface === "composer" && focused
      ? kind === "asset"
        ? "ring-1 ring-[#7c8791]/65 ring-offset-1 dark:ring-offset-[#191c1f]"
        : "ring-1 ring-[#494fdf]/60 ring-offset-1 dark:ring-offset-[#191c1f]"
      : "";
  return [surfaceClass, kindClass, composerFocusClass, focusedClass]
    .filter(Boolean)
    .join(" ");
}

export function EntityToken({
  kind,
  surface,
  children,
  title,
}: {
  kind: EntityTokenKind;
  surface: EntityTokenSurface;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span
      className={entityTokenClassName(kind, surface)}
      data-entity-token
      data-entity-token-kind={kind}
      data-entity-token-surface={surface}
      title={title}
    >
      {children}
    </span>
  );
}
