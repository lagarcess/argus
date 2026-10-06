import { ArrowRight, Plus, ChevronDown } from "lucide-react";
import { businessPath } from "@/lib/business-site";
import { businessContent, type BusinessLocale } from "./content";
import { BusinessHeader } from "./business-header";
import { ProductPreview } from "./product-preview";
import { DemoForm } from "./demo-form";
import styles from "./business.module.css";

function BusinessFooter({
  locale,
  showClosing = true,
}: {
  locale: BusinessLocale;
  showClosing?: boolean;
}) {
  const copy = businessContent[locale];
  const home = businessPath(locale);
  return (
    <footer className={styles.footer}>
      {showClosing && (
        <section className={styles.closing} aria-labelledby="closing-title">
          <h2 id="closing-title">
            {copy.closing.first}
            <br />
            {copy.closing.second}
          </h2>
          <p>{copy.closing.body}</p>
          <a className={styles.button} href={businessPath(locale, "demo")}>
            {copy.navigation.demo}
          </a>
        </section>
      )}
      <div className={styles.footerLinks}>
        <nav aria-label={copy.closing.footerLabel}>
          <a href={home}>{copy.navigation.business}</a>
          <a href={businessPath(locale, "personal")}>
            {copy.navigation.personal}
          </a>
          <a href={`${home}#como-funciona`}>{copy.navigation.approach}</a>
          <a href={`${home}#nosotros`}>{copy.navigation.about}</a>
        </nav>
        <p>{copy.closing.local}</p>
      </div>
      <div className={styles.wordmarkCrop} aria-hidden="true">
        <span>cuadrao</span>
      </div>
    </footer>
  );
}

export function BusinessLanding({ locale }: { locale: BusinessLocale }) {
  const copy = businessContent[locale];
  return (
    <div className={styles.site} lang={locale === "es" ? "es-DO" : "en"}>
      <BusinessHeader locale={locale} />
      <main id="business-main" tabIndex={-1}>
        <section className={styles.hero} aria-labelledby="business-title">
          <h1 id="business-title">
            {copy.hero.first}
            <br />
            {copy.hero.second}
          </h1>
          <p className={styles.heroDescription}>{copy.hero.description}</p>
          <div className={styles.heroActions}>
            <a className={styles.button} href={businessPath(locale, "demo")}>
              {copy.navigation.demo}
            </a>
            <a className={styles.textAction} href="#la-idea">
              {copy.hero.explore}
              <ArrowRight size={20} aria-hidden="true" />
            </a>
          </div>
          <p className={styles.stage}>{copy.hero.stage}</p>
        </section>
        <div className={styles.container}>
          <ProductPreview locale={locale} />
          <section
            className={styles.benefits}
            aria-label={
              locale === "es"
                ? "Lo que estamos construyendo"
                : "What we are building"
            }
          >
            {copy.benefits.map((item) => (
              <article key={item.label}>
                <p className={styles.eyebrow}>{item.label}</p>
                <h2>{item.title}</h2>
                <p>{item.body}</p>
              </article>
            ))}
          </section>
          <section
            className={styles.approach}
            id="como-funciona"
            aria-labelledby="approach-title"
          >
            <div>
              <h2 id="approach-title">{copy.approach.title}</h2>
              <p className={styles.sectionDescription}>{copy.approach.body}</p>
            </div>
            <ol className={styles.steps}>
              {copy.approach.steps.map((step, index) => (
                <li key={step.title}>
                  <span className={styles.stepNumber} aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <h3>{step.title}</h3>
                    <p>{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
          <section
            className={styles.founder}
            id="nosotros"
            aria-labelledby="founder-title"
          >
            <div>
              <p className={styles.eyebrow}>{copy.founder.label}</p>
              <h2 id="founder-title">{copy.founder.title}</h2>
            </div>
            <div className={styles.founderStory}>
              <p>{copy.founder.body}</p>
              <p className={styles.signature}>
                <strong>Lucas</strong>
                <span>{copy.founder.role}</span>
              </p>
            </div>
          </section>
          <section className={styles.faq} aria-label={copy.faqLabel}>
            {copy.faqs.map((faq) => (
              <details key={faq.question}>
                <summary>
                  {faq.question}
                  <Plus size={21} aria-hidden="true" />
                </summary>
                <p>{faq.answer}</p>
              </details>
            ))}
          </section>
        </div>
      </main>
      <BusinessFooter locale={locale} />
    </div>
  );
}

export function DemoPage({ locale }: { locale: BusinessLocale }) {
  const copy = businessContent[locale];
  return (
    <div className={styles.site} lang={locale === "es" ? "es-DO" : "en"}>
      <BusinessHeader locale={locale} page="demo" />
      <main
        id="business-main"
        tabIndex={-1}
        className={`${styles.container} ${styles.demoLayout}`}
      >
        <section className={styles.demoIntro} aria-labelledby="demo-title">
          <h1 id="demo-title">
            {copy.demo.first}
            <br />
            {copy.demo.second}
          </h1>
          <p className={styles.sectionDescription}>{copy.demo.body}</p>
          <div className={styles.demoSteps}>
            {copy.demo.steps.map((step, index) => (
              <details key={step}>
                <summary>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <span>{step}</span>
                  <ChevronDown size={20} aria-hidden="true" />
                </summary>
                <p>{copy.approach.steps[index].body}</p>
              </details>
            ))}
          </div>
        </section>
        <DemoForm locale={locale} />
      </main>
    </div>
  );
}

export function PersonalPage({ locale }: { locale: BusinessLocale }) {
  const copy = businessContent[locale];
  return (
    <div
      className={`${styles.site} ${styles.personalSite}`}
      lang={locale === "es" ? "es-DO" : "en"}
    >
      <BusinessHeader locale={locale} page="personal" />
      <main id="business-main" tabIndex={-1} className={styles.personal}>
        <p className={styles.eyebrow}>{copy.personal.eyebrow}</p>
        <h1>{copy.personal.title}</h1>
        <p>{copy.personal.body}</p>
        <span className={styles.personalStatus}>{copy.personal.status}</span>
        <a className={styles.button} href={businessPath(locale)}>
          {copy.personal.return}
          <ArrowRight size={18} aria-hidden="true" />
        </a>
      </main>
      <BusinessFooter locale={locale} showClosing={false} />
    </div>
  );
}
