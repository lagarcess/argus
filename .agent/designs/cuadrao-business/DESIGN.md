# Cuadrao for business: working design direction

**Status:** Work in progress. High-level direction agreed with Lucas on October 6,
2026, America/Chicago. Exact visual specifications and final copy remain open.
**Scope:** Cuadrao's business-led public website, brand presentation, and first
customer contact. This is not a specification for the business application.

This guide records the decisions from the founder's website discussion. Agreed
direction stays stable until explicitly revised. Suggestions and open choices do
not become approved requirements merely because they appear here.

The [local website build spec](../../../docs/superpowers/specs/2026-10-06-cuadrao-business-website.md)
records the first implementation choices. The [verification report](../../../docs/reports/evidence/cuadrao-business/README.md)
records the resulting pages, checks, and remaining publication needs. These are
reviewable draft choices, not approval of final copy or pixels.

The [authority map](../../../docs/DOCUMENTATION_AUTHORITY.md) owns document roles.
The [MVEE](../../../docs/specs/argus-minimum-viable-ecosystem-experience.md) owns
product experience. Technical contracts and the execution board retain their
owners. This document does not claim features are shipped or authorize publication,
deployment, provider work, or changes to the consumer team's delivery.

## 1. Brand and audience

One Cuadrao brand has two distinct product expressions:

| Name | Agreed role |
| --- | --- |
| Cuadrao LLC | The intended company name, as identified by the founder; formation is underway. Confirm completion before presenting it as an established legal entity. Company information belongs in the appropriate About and footer content. |
| cuadrao | The shared public brand and the consumer product name. |
| cuadrao for business | The business product and the priority for this website work. Business is the founder's main revenue focus. |
| Personal | A clear navigation label for the consumer entrance, not a separate company or newly named product. |

The homepage on `cuadrao.ai` leads with Business while keeping Personal easy to
find. This refines the existing [whole-suite website decision](../../../docs/specs/argus-decision-log.md#launch-shape).
The founder owns the domain. Turning the site on comes later.

The initial audience is Dominican small and medium business owners. Lucas plans
to visit businesses such as ferreterías and small manufacturers to learn which
size and workflow fit best. These are discovery examples, not a locked vertical,
an eligibility limit, or a promise of inventory and manufacturing software.
The earlier service-business and freelancer examples do not restrict that search.

The name expresses having things *cuadrao*: clear, accounted for, and settled.
The intended value is understanding business money and keeping the supporting
work organized. Final positioning and slogans remain open. The site earns trust
through specific explanations, useful previews, and real people. It does not
claim market leadership, exclusivity, or customer outcomes without evidence.

## 2. Language and voice

The site is Spanish-first, with natural Dominican Spanish. Copy is clear,
concise, trustworthy, and direct. Local character comes through familiar business
language and situations, not forced slang in every sentence.

The first screen should help an owner understand who this is for, what problem
it addresses, and what to do next. Examples can explain what entered the business,
what was spent, and what remains pending. These are writing directions, not final
headlines or guarantees about available features.

The [existing language contract](../../../docs/PRODUCT.md#6-language-experience-alpha)
retains English and Latin American Spanish support. Spanish leads the content
and design review. An English launch schedule and the exact language selector
remain open. Content should stay easy to translate.

## 3. Visual character

Business uses a restrained, mostly monochrome direction. It should feel calm,
precise, capable, and human. Generous space, clear hierarchy, quiet dividers,
legible product details, and purposeful motion support that direction.

Personal can be warmer and more expressive. The existing
[Cuadrao native guide](../cuadrao/DESIGN.md) remains its design owner. This lane
does not recolor or redesign the consumer app. The shared wordmark and related
type and control language should make both products recognizable as Cuadrao.
Exact shared assets and tokens still need design work.

Midday is a primary reference for Business restraint. Wise and Revolut inform
audience navigation and financial-product presentation. Phantom informs the
more expressive Personal direction and selected useful details. None is a
template to copy wholesale.

Font families, color values, type sizes, spacing scales, corner radii, dark mode,
and animation timings are not locked. Serif display text with readable sans-serif
body text is a candidate. The quoted startup satire does not select Instrument
Serif, an all-serif interface, fake engagement, or a new company name.

For the first draft, explore the founder-requested oversized `cuadrao` wordmark
cropped at the bottom of the footer. The pattern was visually checked on
[Midday's live homepage](https://midday.ai/) on October 6. Use Cuadrao's own
lettering and proportions, after the final action and useful footer links.
The crop must feel intentional on small screens without horizontal overflow or
clipping functional content. Exact size, crop, and treatment await local review.

## 4. Mobbin is the design research method

Mobbin research applies throughout the website: navigation, page sections,
typography, imagery, product previews, forms, states, footers, mobile layouts,
and small interactions. The named brands are starting points, not a closed list.

For each meaningful design choice, inspect relevant references and keep the
Mobbin link, the useful pattern, why it fits Cuadrao, and what will be adapted or
omitted. Review the actual images. A listing or polished appearance alone does
not prove conversion performance or a top rating. Selections must form one
coherent Cuadrao design across pages.

References inspected during the October 6 discussion:

| Reference | Useful direction |
| --- | --- |
| [Midday comparison page](https://mobbin.com/sites/sections/76493ef8-007e-47f8-971d-60d00fab1961) | Restrained type, whitespace, and clear actions. The competitor-comparison content is not adopted. |
| [Midday founder story](https://mobbin.com/sites/sections/4e86ea75-c67e-4cbf-b1db-5892ed520e4a) and [origin story](https://mobbin.com/sites/sections/1066980e-92c0-4746-b748-07ec0b72ac26) | People, purpose, and the customer problem in plain language. |
| [Wise Business](https://mobbin.com/sites/sections/ecdc2314-63d0-43e8-ac5a-2c9e1d349465) and [Revolut Business](https://mobbin.com/sites/sections/84f53af0-8825-4816-ab6f-0220478a4e81) | Visible Personal and Business entrances with audience-specific content. |
| [Phantom wallet](https://mobbin.com/sites/sections/b52803bf-ff62-4b33-9e92-5a8dfb4bede7) and [connect-at-scale page](https://mobbin.com/sites/sections/0881026c-ca19-43b2-937a-39f37cbb10b9) | Different moods that retain a recognizable brand. Purple glows and crypto imagery are not Cuadrao requirements. |
| [Ramp demo](https://mobbin.com/sites/sections/aa950d43-7969-42f3-a11b-f0890c66fdae) | Explain the meeting and show the product alongside the action. Its duration, claims, and customer logos do not transfer to Cuadrao. |

## 5. First website experience

The business website is the active focus. Personal gets a small skeleton and a
clear entrance. Consumer TestFlight, beta access, and app delivery remain outside
this lane. A placeholder must not imply that public consumer access is available.

The starting reality is zero clients, active founder outreach, and a business
product whose backend still needs to be built. The immediate deliverable is a
local landing-page skeleton for Lucas to review. It must communicate the value
quickly and make booking a conversation the primary next step. There are no
customer testimonials, customer-logo strips, adoption counts, or customer results
to publish. Honest illustrative previews and a real founder can support trust.

Business uses a demo-led, founder-assisted approach. Lucas will work personally
with early customers to establish a reliable workflow and learn what fits.
Pricing is not settled. There is no published pricing table or empty Pricing
page in the initial direction. This does not establish free access, pilot fees,
contract terms, or a permanent custom-pricing model.

"Agenda una demo" is a working action label. The meeting description must match
what can actually be shown. "Hablemos de tu negocio" remains a suggested label
if the first conversation precedes a product demonstration. Final wording and
the calendar, WhatsApp, or request-form destination remain undecided.

For local review, the action can open a lightweight form prototype. It must say
that nothing is sent or booked and must not show a false submission confirmation.
A working booking destination is needed before public use, but does not block
the local design. The domain, backend, and external integrations come later.

The exact page map is open. The initial design needs to explain the business
value, show an honest preview, provide an About or story area, and lead to a
clear next step. Supported capabilities, planned work, and sample data must be
distinguishable. Product scope still comes from its assigned contracts.

## 6. About and founder story

The founder supplied three screenshots of an eight-point About-page template
on October 6. They are content references, not verified SEO guidance. Lucas
approved selecting only the parts that fit Cuadrao. He has a personal photograph
for this page; the portrait itself has not been supplied in this discussion.

The working content direction is:

| Content | Cuadrao treatment |
| --- | --- |
| Clear introduction | Explain what Cuadrao helps with and who it serves in a short opening. |
| What it does | Describe the few relevant customer jobs and their outcomes. Availability must be accurate. |
| Why this approach | Explain specific differences we can support. No required count of five or mandatory competitor comparisons. |
| Who it is for | Speak to the current business audience while the pilot refines fit. Do not invent employee ranges or customer segments. |
| Founder and origin | Use Lucas's portrait and a short, factual story about the problem, why he is building Cuadrao, and relevant experience. A supplied LinkedIn or other professional profile can support the story. |
| How customers work with us | Explain personal involvement and the next step. Channels, response times, onboarding steps, and service commitments need confirmation. |
| Company facts | Include only useful, confirmed information. Unknown dates, headquarters, client counts, prices, and contract terms stay unpublished. |
| Common questions | Answer actual buyer concerns briefly. Add a section when there are useful answers, not to meet a template quota. |

The finished page may combine these topics. It does not need eight sections.
Clear headings and semantic HTML are appropriate. Tables or definition lists
are useful only when the content benefits. Claims of guaranteed AI-search
visibility or E-E-A-T gains are not adopted. Neither are invented customer
logos, engagement, quantitative benefits, or founder credentials.

Keep the founder section secondary to the customer problem and booking action:
a portrait, a few sentences, and one useful profile link are sufficient for the
first draft. Lucas shared experience at Meta and Google, in machine learning and
data science, and part-time reinforcement-learning startup work. These are
founder-supplied background, not approved final biography copy. Select only what
helps explain his ability and motivation; confirm exact role wording before
publication. Do not imply employer endorsement or turn this into a résumé or
employer-logo section. His precise motivation should use his own account rather
than an invented origin story. Missing portrait and profile URLs do not block
the local layout.

## 7. Web foundation and quality

The [approved web stack](../../../docs/ARCHITECTURE.md#approved-platform-direction)
remains Next.js with React and TypeScript. Tailwind is already present in the
[web package](../../../web/package.json). This is the proposed foundation for
the website, not permission to replace existing routes or shared styling.
Deployment follows the [existing architecture](../../../docs/ARCHITECTURE.md#18-deployment-shape).
No new hosting provider or separate application topology is selected here.

The agreed quality goal is a fluid, fast site on phones, tablets, and desktops.
Flexible layouts, readable text, touch and keyboard access, visible focus, and
reduced-motion support belong in the initial design. Exact breakpoint layouts
come later. Universal device compatibility is a goal, not a tested claim.

The proposed implementation keeps marketing content mostly prerendered or
server-rendered, with browser code limited to needed interactions. Images,
fonts, motion, and third-party widgets must fit the performance goal. Search
metadata and useful WhatsApp link previews are planned details. Numeric budgets,
browser coverage, analytics, and acceptance checks still need a bounded build spec.

## 8. Open choices and maintenance

The next design work resolves these choices without reopening the agreed direction:

- The first repeatable customer job, business size, and pilot fit, informed by visits.
- Final positioning, headlines, Spanish product descriptor, and navigation labels.
- Wordmark treatment, font pair, palette, components, and representative layouts.
- What the initial demo shows, its destination, and the follow-up process.
- Page map, English publication scope, portrait, biography, and confirmed company facts.
- Implementation boundaries, performance targets, browser checks, and eventual publication.

These refinements do not block the first local design. Start with the agreed
business audience, Spanish-first voice, restrained visual direction, honest
preview content, and one clear demo action. Use local placeholders for missing
assets and contact details. Resolve the live booking route, public claims,
company facts, and publication details before making the site public.

Update this guide when Lucas approves a design choice. Keep one owner for each
rule and link to product, technical, and release owners rather than copying
their contracts here. A reference or proposed layout becomes a lock only through
an explicit decision. The consumer guide remains independently owned.
