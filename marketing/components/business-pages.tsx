import Image from "next/image";
import { ArrowDown, ArrowUpRight } from "lucide-react";
import type { BusinessLocale } from "./content";
import { businessContactEmail, siteCopy } from "./site-copy";
import { BusinessHeader } from "./business-header";
import { BusinessHeroVisual } from "./business-hero-visual";
import heroStyles from "./business-hero-visual.module.css";
import { BusinessCapabilities } from "./business-capabilities";
import { MoneyStory } from "./money-story";
import { PlanStory } from "./plan-story";
import { WorkStory } from "./work-story";
import { SupportingRecords } from "./supporting-records";
import { BusinessSurfaces } from "./business-surfaces";
import { ProductPreview } from "./product-preview";
import { ContactForm } from "./contact-form";
import { PersonalEarlyAccess } from "./personal-early-access";
export { PrivacyPage } from "./privacy-page";
import { BusinessFooter, ContactLink } from "./business-footer";
import styles from "./business.module.css";

function FounderIdentity({ locale }: { locale: BusinessLocale }) {
  return (
    <div className={styles.founderIdentity}>
      <Image
        className={styles.founderPortrait}
        src="/cuadrao-site/lucas-garces.png"
        alt={locale === "es" ? "Retrato de Lucas Garcés" : "Portrait of Lucas Garcés"}
        width={96}
        height={96}
        sizes="96px"
      />
      <Image
        className={styles.founderSignature}
        src="/cuadrao-site/lucas-garces-signature.png"
        alt="Lucas Garcés"
        width={1942}
        height={809}
        sizes="200px"
      />
    </div>
  );
}

export function BusinessLanding({ locale }: { locale: BusinessLocale }) {
  const c = siteCopy[locale];
  return (
    <div
      className={styles.site}
      lang={locale === "es" ? "es-DO" : "en"}
      id="top"
    >
      <BusinessHeader locale={locale} />
      <main id="business-main" tabIndex={-1}>
        <section className={heroStyles.hero} aria-labelledby="business-title">
          <div className={heroStyles.copy}>
            <h1 id="business-title">{c.title[0]}<br />{c.title[1]}</h1>
            <p className={heroStyles.description}>{c.description}</p>
            <div className={heroStyles.actions}>
              <ContactLink locale={locale} />
              <a className={styles.textAction} href="#el-producto">{c.explore}<ArrowDown size={17} aria-hidden="true" /></a>
            </div>
            <p className={heroStyles.audience}>{c.audience}</p>
          </div>
          <BusinessHeroVisual locale={locale} />
        </section>
        <BusinessCapabilities locale={locale} />
        <MoneyStory locale={locale} />
        <PlanStory locale={locale} />
        <WorkStory locale={locale} />
        <ProductPreview locale={locale} />
        <SupportingRecords locale={locale} />
        <BusinessSurfaces locale={locale} />
        <section
          className={styles.approach}
          id="como-funciona"
          aria-labelledby="approach-title"
        >
          <div className={styles.approachHeading}>
            <div>
              <p className={styles.sectionIndex}>
                05 / {locale === "es" ? "EL PRIMER PILOTO" : "THE FIRST PILOT"}
              </p>
              <h2 id="approach-title">{c.approachTitle}</h2>
            </div>
            <p>{c.approachBody}</p>
          </div>
          <ol className={styles.steps}>
            {c.steps.map((item, i) => (
              <li key={item.title}>
                <span>{String(i + 1).padStart(2, "0")}</span>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </li>
            ))}
          </ol>
        </section>
        <section
          className={`${styles.founder} ${styles.founderLetter}`}
          id="nosotros"
          aria-labelledby="founder-title"
        >
          <div>
            <p className={styles.sectionIndex}>{c.founderLabel}</p>
            <h2 id="founder-title">{c.founderTitle}</h2>
          </div>
          <div className={styles.founderStory}>
            <p className={styles.salutation}>{locale === "es" ? "Hola," : "Hello,"}</p>
            {c.founderParagraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
            <p className={styles.letterSignoff}>{locale === "es" ? "Gracias por leer," : "Thank you for reading,"}</p>
            <FounderIdentity locale={locale} />
          </div>
        </section>
        <section className={styles.faq} id="preguntas" aria-labelledby="faq-title">
          <div className={styles.faqHeading}>
            <p className={styles.sectionIndex}>{c.faqLink}</p>
            <h2 id="faq-title">{c.faqTitle}</h2>
            <p>{c.faqBody}</p>
          </div>
          <div className={styles.faqItems}>
            {c.faq.map((item) => (
              <details key={item.question}>
                <summary>{item.question}<span aria-hidden="true">+</span></summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        </section>
      </main>
      <BusinessFooter locale={locale} business />
    </div>
  );
}

export function ContactPage({ locale }: { locale: BusinessLocale }) {
  const c = siteCopy[locale];
  return (
    <div
      className={styles.site}
      lang={locale === "es" ? "es-DO" : "en"}
      id="top"
    >
      <BusinessHeader locale={locale} page="contact" />
      <main id="business-main" tabIndex={-1} className={styles.demoLayout}>
        <section className={styles.demoIntro}>
          <h1>{c.contactLead}</h1>
          <p>{c.contactBody}</p>
          <p className={styles.contactPrivacy}>{c.contactNote}</p>
        </section>
        <ContactForm locale={locale} />
        <aside className={styles.contactDetails} aria-label={c.contact}>
          <div className={styles.directContact}>
            <p>{c.emailInvitation}</p>
            <a className={styles.textAction} href={`mailto:${businessContactEmail}`}>{businessContactEmail}<ArrowUpRight size={18} aria-hidden="true" /></a>
            <small>{c.emailHelp}</small>
          </div>
          <div className={styles.contactPerson}>
            <FounderIdentity locale={locale} />
            <p>{c.founderNote}</p>
          </div>
        </aside>
      </main>
      <BusinessFooter locale={locale} showClosing={false} business />
    </div>
  );
}

export function PersonalPage({ locale }: { locale: BusinessLocale }) {
  return (
    <div
      className={`${styles.site} ${styles.personalSite}`}
      lang={locale === "es" ? "es-DO" : "en"}
      id="top"
    >
      <BusinessHeader locale={locale} page="personal" />
      <main id="business-main" tabIndex={-1}>
        <PersonalEarlyAccess locale={locale} />
      </main>
      <BusinessFooter locale={locale} showClosing={false} personal />
    </div>
  );
}
