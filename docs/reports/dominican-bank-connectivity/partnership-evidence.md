# Bank partnership evidence proposal

This file treats the founder's partnership strategy as a hypothesis to test, not a plan to execute. The hypothesis has four steps. A useful consumer product creates demand. Demand becomes evidence a bank can check. The evidence earns a partnership. The partnership brings better connectivity than files or credential-based access.

Nothing here authorizes analytics, outreach, a data-sharing agreement, or a sponsored placement. Argus's closed analytics event registry, merged in pull request 702, still owns every measured event. Each measure below would need a registry change, a privacy review, and a founder decision before it exists.

## What a bank would need to see

A bank's first question is whether Argus users are its customers and whether they would use a sanctioned connection. The second question is what a connection would cost the bank in risk and support. The evidence below answers both without exposing any individual.

| Evidence | What it shows the bank | How Argus could measure it without new private data |
| --- | --- | --- |
| Consenting active users by institution | How many of the bank's customers use Argus for their money | Count people who imported a statement or file attributed to the institution in the last 30 and 90 days, and who agreed to be counted in partner reporting |
| Repeat import and refresh demand | Whether people want fresher data than monthly files give | Share of those people who import again within 35 days, and the median number of days between imports |
| Import completion and reliability | Whether the bank's own files serve its customers | Share of imports that reach confirmation, by institution and format. Parse failures and rows that needed manual correction per 100 rows. |
| Reduction in recording effort | Whether imports replace manual work | Manual entries per active person before and after their first import. Owner review actions per 100 imported rows. |
| Support and reconnection burden | The cost a connection moves onto the bank and onto Argus | Support contacts per 100 imports. For any later connection, re-authentication events per connection-month. |
| Reported value | Whether customers would ask the bank for a direct connection | An opt-in in-product question, reported only as counts |
| Consented product referrals | Commercial value to the bank, where the person chose it | Only referrals a person explicitly started, with the sponsored label shown, counted in aggregate. No lead lists and no financial records leave Argus. |

## Keep the measures aggregate and private

Every measure above uses metadata Argus would already hold for the product to work: the institution a file came from, import timestamps, confirmation counts, and review actions. None of it needs an amount, a merchant, a description, or an account number. Seven rules keep it that way.

1. Report counts and rates only, never rows about a person.
2. Suppress small cells. Dominican counsel and the founder set the minimum cell size before any report leaves Argus.
3. Ask separately for consent to be counted in partner reporting. Using the product does not imply it.
4. Never send a bank a list of its customers who use Argus. Identity is exactly what a bank would want and exactly what the person did not agree to share.
5. Keep amounts, descriptions, balances, and document contents out of analytics, as MVEE section 5 already requires.
6. Separate the analytics owner from the partner-reporting owner, so a report cannot quietly widen what analytics collects.
7. Keep household data inside the household. A partner's consent never counts the other partner's private accounts.

## Why a bank might say yes

The incentives below are plausible. None of them is confirmed by a Dominican bank.

- **Security.** A sanctioned, scoped, revocable connection replaces customers typing passwords into third parties. The Bridge terms show that credential-based access already exists in the Dominican market.
- **Readiness for open finance.** The Superintendencia de Bancos has published statements about open-finance implementation. A bank that has already run a scoped data-sharing pilot learns before any mandate arrives.
- **Lower support load.** Customers who can export clean files, or connect through a sanctioned channel, stop asking branches for printed statements.
- **Distribution.** A clearly labeled product placement can reach customers who are already comparing options inside Argus.
- **Insight at the aggregate level.** A bank may value anonymous, aggregate evidence about how its customers organize money. Argus must decide whether it offers that, because the same data is what users trust Argus to protect.

## Why a bank might say no

- **Liability.** A bank will ask who pays when a connected app leaks data or enables fraud. Argus has no certification, insurance, or audit history today.
- **Banking secrecy.** Article 56 of Ley 183-02 governs what a bank may disclose. A bank will want its counsel's view on customer-authorized disclosure before any pilot.
- **Third-party risk rules.** A supervised bank that relies on an outside provider applies its own third-party and cybersecurity rules. Those rules can require due diligence, contracts, and supervisor notification.
- **Competition.** Argus discovery could steer the bank's customers to competitors. A bank may ask for placement terms that compromise the independence of comparisons.
- **Scale.** A small user base does not justify API development, security review, and legal work.
- **Continuity.** A bank will ask what happens to its customers' data if Argus stops operating.

## Sponsored products do not buy data access

A sponsored placement is a marketing agreement. Account-data access is a security, legal, and customer-consent agreement. Different teams inside a bank own each one, with different risk tolerances. Paying for placement does not create a lawful basis to share account data, and it does not remove any objection above.

Keep the two agreements separate. Mixing them creates a conflict of interest. A bank that both sponsors placements and supplies data may expect its products to rank higher, and Argus users would have no way to know.

## Is a separate connectivity business viable?

The idea of Argus eventually selling connectivity to other apps has no supporting evidence yet. Treat it as speculative and keep it apart from the immediate recommendation.

A connectivity business sells five things, and each has a cost Argus does not carry today.

| What customers buy | What it requires | Evidence today |
| --- | --- | --- |
| Uptime per institution | Monitoring and fixes for every bank connector, around the clock | None. Argus runs no connector. |
| Support | A support team for both the apps and their end users | None |
| Security assurance | Audits such as SOC 2 or ISO 27001, penetration tests, breach response | None |
| Liability coverage | Contracts, insurance, and capital to absorb losses | None |
| Contractual coverage | Agreements with banks, or a regulated role in an open-finance framework | None. The Dominican framework is not in force. |

A local competitor already exists. Bridge Labs, S.R.L. publishes a developer API, a connection widget, and self-serve plans for Dominican bank data, using credential-based access under its own terms. Its public pages name no supported bank and claim no regulatory status.

Revisit the idea only when all four conditions hold.

1. At least one bank agreement or a regulated role exists.
2. Argus's own connectors have run reliably for months, with measured re-authentication and failure rates.
3. Other apps ask for the service unprompted.
4. The unit economics per active connection are known from real costs, not estimates.

Until then, keep connectivity inside Argus as a replaceable retrieval method, as the integration map describes.
