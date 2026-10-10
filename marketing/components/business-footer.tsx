import { Fragment } from "react";
import { ArrowUpRight } from "lucide-react";
import { businessPath } from "@/lib/site-routes";
import { businessContent, type BusinessLocale } from "./content";
import { businessContactEmail, siteCopy } from "./site-copy";
import styles from "./business.module.css";
import shell from "./touchup-shell.module.css";
import { FooterMotion } from "./footer-motion";

export function ContactLink({
  locale,
  light = false,
}: {
  locale: BusinessLocale;
  light?: boolean;
}) {
  return (
    <a
      className={`${styles.button} ${light ? styles.buttonLight : ""}`}
      href={businessPath(locale, "contact")}
    >
      {siteCopy[locale].cta}
      <ArrowUpRight size={19} aria-hidden="true" />
    </a>
  );
}

export function BusinessFooter({
  locale,
  showClosing = true,
  business = false,
  personal = false,
}: {
  locale: BusinessLocale;
  showClosing?: boolean;
  business?: boolean;
  personal?: boolean;
}) {
  const c = siteCopy[locale];
  const FooterContent = personal ? Fragment : FooterMotion;
  return (
    <footer
      className={`${styles.footer} ${business ? styles.businessFooter : ""} ${shell.footer}`}
    >
      <FooterContent>
      {showClosing && (
        <section className={styles.closing} aria-labelledby="closing-title">
          <div>
            <span className={styles.sectionIndex}>
              {locale === "es" ? "EL PRÓXIMO PASO" : "THE NEXT STEP"}
            </span>
            <h2 id="closing-title">{c.closingTitle}</h2>
          </div>
          <div>
            <p>{c.closingBody}</p>
            <ContactLink locale={locale} />
            <small>{c.stage}</small>
          </div>
        </section>
      )}
      {business ? (
        <div className={styles.businessFooterGrid}>
          <div className={styles.footerIdentity}>
            <a href={businessPath(locale)} className={styles.wordmark}>
              cuadrao
            </a>
            <span>{c.business}</span>
            <p>{c.footerTag}</p>
          </div>
          <nav aria-label={c.footerExplore}>
            <span>{c.footerExplore}</span>
            <a href={`${businessPath(locale)}#el-producto`}>{c.business}</a>
            <a href={`${businessPath(locale)}#la-idea`}>{c.explore}</a>
            <a href={`${businessPath(locale)}#preguntas`}>{c.faqLink}</a>
            <a href={businessPath(locale, "personal")}>{c.personal}</a>
          </nav>
          <nav aria-label={c.footerTalk}>
            <span>{c.footerTalk}</span>
            <a href={`${businessPath(locale)}#nosotros`}>{c.about}</a>
            <a href={businessPath(locale, "contact")}>{c.contact}</a>
            <a href={businessPath(locale, "privacy")}>{c.privacyLabel}</a>
            <a
              href="https://www.linkedin.com/in/lucasgarces"
              target="_blank"
              rel="noopener noreferrer"
            >
              Lucas · LinkedIn <ArrowUpRight size={14} aria-hidden="true" />
            </a>
          </nav>
          <div className={styles.footerAvailability}>
            <p>{c.stage}</p>
            <a href="#top" className={styles.backTop}>
              {c.top}
              <ArrowUpRight size={16} aria-hidden="true" />
            </a>
          </div>
        </div>
      ) : (
        <div className={styles.footerLinks}>
          <a
            href={businessPath(locale, personal ? "personal" : "home")}
            className={styles.wordmark}
          >
            cuadrao
          </a>
          <p>
            {personal
              ? locale === "es"
                ? "Tus finanzas, en orden."
                : "Your finances, in order."
              : c.footerTag}
          </p>
          <nav aria-label={businessContent[locale].closing.footerLabel}>
            <a href={businessPath(locale)}>{c.business}</a>
            <a href={businessPath(locale, "personal")}>{c.personal}</a>
            <a
              href={
                personal
                  ? `mailto:${businessContactEmail}`
                  : businessPath(locale, "contact")
              }
            >
              {personal ? businessContactEmail : c.contact}
            </a>
            <a href={businessPath(locale, "privacy")}>{c.privacyLabel}</a>
          </nav>
          <div>
            <p>
              {personal
                ? locale === "es"
                  ? "Cuadrao Personal · acceso anticipado"
                  : "Cuadrao Personal · early access"
                : c.footerLocal}
            </p>
            <a href="#top" className={styles.backTop}>
              {c.top}
              <ArrowUpRight size={16} aria-hidden="true" />
            </a>
          </div>
        </div>
      )}
        <div className={styles.wordmarkCrop} aria-hidden="true">
          <span>cuadrao</span>
        </div>
      </FooterContent>
    </footer>
  );
}
