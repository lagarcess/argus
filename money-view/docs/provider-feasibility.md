# Money placement provider feasibility

Verified on 2026-09-20 from public, official Superintendencia de Bancos (SB)
and Banco Central de la República Dominicana (BCRD) pages. No credentialed API
request was made. No API key was created, read, or used.

## Decision summary

The SB Statistics API can supply historical deposit balances and weighted
average rates by supervised entity, deposit instrument, currency, reporting
period, and several customer classifications. It does not document a deposit
maturity, a publication date for each API row, or enough rate semantics to
calculate a trustworthy end value.

The real SB adapter must therefore remain fail closed until a credentialed
sample and official metadata establish the rate unit and annualization. Even
then, SB rows cannot become calculation-ready term-deposit observations unless
another verified source supplies maturity. Mock data is authorized for the
default-off experience, but it must be visibly synthetic and must never be
presented as SB or BCRD data.

Consumer inflation is not part of the SB API catalog. BCRD is the official
source, but its API portal is access-gated and its endpoint contract could not
be verified publicly. Do not create a production BCRD adapter from an assumed
schema.

## Verified SB transport contract

Canonical deposit-detail endpoint:

```text
GET https://apis.sb.gob.do/estadisticas/v2/captaciones/detalle
```

Official endpoint documentation:

<https://desarrollador.sb.gob.do/api-details#api=estad-sticas-del-sistema-financiero-con-paginacion&operation=detalleCaptaciones>

Request inputs documented by SB:

| Input | Required | Meaning |
| --- | --- | --- |
| `periodoInicial` | yes | `YYYY-MM`; documented as a template parameter |
| `periodoFinal` | no | `YYYY-MM` |
| `entidad` | no | array of short entity names, such as `ADEMI` or `APAP` |
| `tipoEntidad` | no | array of short entity-type names, such as `BM` or `BAyC` |
| `persona` | no | array of long person types, such as `Persona Juridica` or `Persona Fisica` |
| `instrumento` | no | array of long instrument names, such as `LETRAS` or `CUENTAS BÁSICAS DE NÓMINA` |
| `divisa` | no | array of short currency codes, such as `EUR` or `DOP` |
| `paginas` | no | page number, `int32` |
| `registros` | no | requested record count, `int32` |

Authentication is a subscription key in this request header:

```text
Ocp-Apim-Subscription-Key: <subscription key>
```

The developer portal says a user must register, select a plan, and generate an
API key. SB's official tutorial confirms the header and the v2 base URL:

<https://medium.com/@SB-ESTUDIOS/usar-el-api-v2-de-estad%C3%ADstica-desde-python-y-r-857bf76fdf7f>

Responses use JSON. Pagination metadata is returned in the `x-pagination`
response header. The official tutorial documents these members:

- `CurrentPage`
- `RequestRecords`
- `RecordsResponse`
- `HasPrevious`
- `HasNext`
- `TotalRecords`
- `TotalPages`

The tutorial recommends intermediate storage and incremental updates rather
than request-time use. It says a full deposit/credit detail pull can contain
roughly 10 to 15 million records with 26 columns. The production shape should
therefore be scheduled ingestion into Argus-owned storage, never a live API
call while a person waits.

## Exact documented SB response fields

The `DetallesCaptaciones` response schema documents every field as optional.
The raw adapter must preserve these wire names and types exactly:

| Raw field | Documented type |
| --- | --- |
| `periodo` | string |
| `tipoEntidad` | string |
| `entidad` | string |
| `region` | string |
| `provincia` | string |
| `persona` | string |
| `genero` | string |
| `tipoCliente` | string |
| `instrumentoCaptacion` | string |
| `moneda` | string |
| `divisa` | string |
| `partidaNivel1` | string |
| `partidaNivel2` | string |
| `publicoPrivadoNivel1` | string |
| `publicoPrivadoNivel2` | string |
| `financieroNoFinanciero` | string |
| `residenteNoResidente` | string |
| `componente` | string |
| `instrumentoMedio` | string |
| `contraParte` | string |
| `situacionNivel1` | string |
| `situacionNivel2` | string |
| `cantidadInstrumento` | integer (`int32`) |
| `balance` | number (`double`) |
| `tasaPrimedioPonderadoPorBalance` | number (`double`) |
| `tasaPrimedioPonderado` | number (`double`) |

The misspelling `Primedio` is present in the official deposit-detail schema.
It is part of the external wire contract. A different SB endpoint uses the
corrected `Promedio` spelling, so transport parsing must be endpoint-specific
instead of silently assuming one shared spelling.

## Supported canonical mapping

| Product fact | Verified SB source | Boundary rule |
| --- | --- | --- |
| institution | `entidad` | Preserve the raw value; resolve display metadata separately if needed. |
| product/instrument category | `instrumentoCaptacion` | Describe it as a category, not a named retail offer. |
| currency | `divisa` | Examples are `DOP` and `EUR`. Preserve `moneda` separately until its relationship to `divisa` is verified from real rows. |
| effective reporting period | `periodo` | Store as `effective_period`; do not convert it to a publication date. |
| observed balance | `balance` | Preserve raw numeric value and validate before use. |
| average rate paid on balances | `tasaPrimedioPonderadoPorBalance` | This is the only safe user wording. It is not an offered rate or APY. |
| source URL | canonical endpoint above | This identifies the authenticated source endpoint; it does not make the row publicly retrievable. |
| retrieval time | Argus ingestion clock | Store as `retrieved_at`; never substitute it for publication or effective period. |

SB describes the endpoint as supplying balances and weighted average rates.
Its official deposit publication defines passive rates as the rates the
financial system pays people for placing resources in banks:

<https://sb.gob.do/prensa/captaciones-del-sistema-financiero-ascienden-a-rd-25-billones-en-junio-de-2023-crecimiento-interanual-de-13/>

## Facts the SB API does not support

### Publication date

The response has `periodo`; it has no publication or release date. `periodo`
is a reporting period and `retrieved_at` is an Argus observation time. Neither
is `published_on`.

SB's publication pages have real publication dates, for example:

<https://www.sb.gob.do/publicaciones/publicaciones-tecnicas/>

Those dates belong to the named publications. They must not be copied onto API
rows unless the publication is the actual source of that row. For API data,
`published_on` must remain nullable and explicitly unknown.

### Maturity or term

The request and response schemas contain no `term`, `plazo`, maturity date, or
maturity bucket. `situacionNivel1` and `situacionNivel2` are undocumented
classification fields and must not be relabeled as term.

SB publications sometimes discuss term buckets, but that does not make term a
dimension of the API row. A production comparison requiring a requested
horizon needs a separate verified offer or maturity source.

### Rate semantics

The OpenAPI documentation exposes two rate doubles but gives neither one a
field description. It does not establish:

- whether values are percentages or decimal fractions;
- whether the rate is annual, monthly, nominal, or effective;
- a compounding convention;
- whether the second rate is weighted by another measure;
- whether the reported rate can be applied prospectively to a deposit;
- whether a given row describes an open product available to a new customer.

The name `tasaPrimedioPonderadoPorBalance` supports the label "average rate
paid on balances." It does not support an end-value calculation. Rate
normalization must fail until a credentialed sample and official metadata or
support answer prove the unit and annualization.

The API also lacks verified product fees, taxes, minimum balances, eligibility,
withdrawal rules, liquidity, deposit-guarantee treatment, compounding, and
reinvestment behavior.

## Inflation source boundary

The complete public SB API catalog covers deposits, credit portfolios, entity
details, financial statements, banking indicators, complaints, solvency,
banking subagents, and credit-card rates and fees. Its indicator operations are
banking-system indicators such as stressed delinquency, credit risk, and
financial indicators. It exposes no consumer price index or consumer
inflation operation.

BCRD is the official source for the national consumer price index and consumer
inflation:

- Official prices and IPC datasets: <https://www.bancentral.gov.do/a/d/2534-precios>
- Official IPC variation calculator: <https://bancentral.gov.do/a/ipc-consulta>
- Official API portal: <https://apibcrd.bancentral.gov.do/>

The BCRD API portal requires sign-in/access. Its current endpoint path,
authentication contract, response schema, quotas, and publication-date fields
were not publicly verifiable in this review. A BCRD production adapter is
blocked on authorized access and a captured official schema. Public BCRD IPC
reports can support cited human-readable evidence, but they are not a substitute
for a verified machine-ingestion contract.

## Fail-closed adapter recommendation

Keep source transport, provenance, and calculation truth as separate layers.
One useful mental model is a customs checkpoint: the raw shipment remains
intact, while only items with complete paperwork may enter the calculation
engine.

1. **Raw source record.** Persist the exact SB payload and wire field names,
   including `tasaPrimedio...`, plus the canonical endpoint, retrieval time,
   response/reporting period, and an ingestion correlation id. Never add a
   term or publication date to this record.
2. **Normalized candidate.** Map only supported facts: institution, instrument
   category, currency, effective period, balance, and the raw observed rate.
   Carry validation issues such as `missing_maturity`,
   `unknown_rate_unit`, `unknown_annualization`, and
   `missing_publication_date` as typed outcomes rather than prose guesses.
3. **Calculation-ready observation.** Construct this type only when currency,
   a verified maturity matching the requested horizon, rate unit,
   annualization, and calculation convention are all present and sourced.
   No current SB row can cross this gate because maturity and rate semantics
   are absent.
4. **Provider interface.** Return raw provenance plus either a validated
   calculation-ready observation or a structured rejection. Keep the contract
   provider-neutral so a future United States source can implement it, but do
   not add a United States implementation in this lane.

With no keys configured, the real provider must report unavailable and make no
network request. It must not fall back to fixtures under a real-source label.
The default-off experience may select an explicit synthetic provider instead.

## Synthetic fixture rules

Mock data is authorized. It may declare the missing values needed to exercise
the product, including an explicit maturity, rate unit, annualization, and
compounding convention. Every synthetic dataset and returned row must carry an
unambiguous synthetic origin, for example `data_origin = "synthetic"`, and the
UI/evidence must present it as modeled example data.

Synthetic fixtures must not:

- use SB or BCRD as the stated provider;
- copy the official endpoint into `source_url` as though the fixture came from it;
- invent `published_on`, retrieval evidence, institution provenance, or a term;
- silently activate when real credentials are missing;
- be eligible for a real-data or customer-ready evidence claim.

For synthetic rows, `source_url` and `published_on` should be null. A fixture id
and fixture version provide local reproducibility without manufacturing public
provenance.

## Meaning of "best option"

The founder-approved definition is the highest modeled end value among
comparable deposits in the same currency and requested horizon, with no FX or
reinvestment assumption and with taxes and fees excluded unless verified.

That definition is valid for synthetic fixtures that explicitly declare all
calculation inputs. It is not yet valid for SB data because term and rate
semantics are missing. Until those gaps close, an SB-backed view may only make
the narrower historical claim: "highest reported average rate paid on balances
for the same instrument category, currency, customer segment, and reporting
period." It must not call that institution's product the best offer for the
person.

## Preconditions for a real provider

Before enabling an SB production adapter:

- obtain authorized subscription access without placing a key in source code;
- capture a small official response sample without logging the key;
- verify current field vocabularies, nullability, numeric scale, and period
  coverage;
- obtain official confirmation of rate units and annualization;
- choose and verify a separate maturity/offer source if modeled end value is
  required;
- keep `published_on` null unless the row source supplies a real publication
  date;
- document permitted reuse before presenting the data to users.

Before enabling BCRD inflation ingestion, capture its official endpoint,
authentication, schema, quota, period semantics, and publication metadata from
authorized access. Until then, BCRD support remains a source-design placeholder,
not a production adapter.
