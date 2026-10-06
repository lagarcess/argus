"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { businessPath, type BusinessPage } from "@/lib/business-site";
import { businessContent, type BusinessLocale } from "./content";
import styles from "./business.module.css";

export function BusinessHeader({
  locale,
  page = "home",
}: {
  locale: BusinessLocale;
  page?: BusinessPage;
}) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLElement>(null);
  const copy = businessContent[locale].navigation;
  const home = businessPath(locale);

  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLAnchorElement>("a")?.focus();
    const closeOnEscape = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const languageLinks = (
    <span className={styles.languages} aria-label={copy.language}>
      {(["es", "en"] as const).map((language) => (
        <a
          key={language}
          href={businessPath(language, page)}
          hrefLang={language}
          lang={language}
          aria-current={locale === language ? "true" : undefined}
        >
          {language.toUpperCase()}
        </a>
      ))}
    </span>
  );

  return (
    <>
      <a className={styles.skip} href="#business-main">
        {copy.skip}
      </a>
      <header className={styles.header}>
        <a
          className={styles.wordmark}
          href={home}
          aria-label="Cuadrao Business"
        >
          cuadrao
        </a>
        <nav className={styles.desktopNav} aria-label={copy.label}>
          <div className={styles.audienceNav}>
            <a
              className={page !== "personal" ? styles.activeNav : undefined}
              href={home}
              aria-current={page === "home" ? "page" : undefined}
            >
              {copy.business}
            </a>
            <a
              className={page === "personal" ? styles.activeNav : undefined}
              href={businessPath(locale, "personal")}
              aria-current={page === "personal" ? "page" : undefined}
            >
              {copy.personal}
            </a>
          </div>
          <div className={styles.utilityNav}>
            {page === "demo" ? (
              <a href={home} className={styles.backLink}>
                {copy.back}
                <ArrowUpRight size={16} aria-hidden="true" />
              </a>
            ) : (
              <>
                <a href={`${home}#como-funciona`}>{copy.approach}</a>
                <a href={`${home}#nosotros`}>{copy.about}</a>
              </>
            )}
            {languageLinks}
            {page !== "demo" && (
              <a
                className={styles.buttonSmall}
                href={businessPath(locale, "demo")}
              >
                {copy.demo}
              </a>
            )}
          </div>
        </nav>
        <button
          ref={trigger}
          type="button"
          className={styles.menuButton}
          aria-label={open ? copy.close : copy.menu}
          aria-expanded={open}
          aria-controls="business-mobile-menu"
          onClick={() => setOpen(!open)}
        >
          {open ? (
            <X size={23} aria-hidden="true" />
          ) : (
            <Menu size={23} aria-hidden="true" />
          )}
        </button>
        {open && (
          <nav
            ref={menu}
            id="business-mobile-menu"
            className={styles.mobileNav}
            aria-label={copy.label}
            onClick={(event) => {
              if ((event.target as HTMLElement).closest("a")) setOpen(false);
            }}
          >
            <a href={home} aria-current={page === "home" ? "page" : undefined}>
              {copy.business}
            </a>
            <a
              href={businessPath(locale, "personal")}
              aria-current={page === "personal" ? "page" : undefined}
            >
              {copy.personal}
            </a>
            <a href={`${home}#como-funciona`}>{copy.approach}</a>
            <a href={`${home}#nosotros`}>{copy.about}</a>
            {languageLinks}
            <a className={styles.button} href={businessPath(locale, "demo")}>
              {copy.demo}
            </a>
          </nav>
        )}
      </header>
    </>
  );
}
