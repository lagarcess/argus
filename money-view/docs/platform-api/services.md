# Local service workflows

All paths use `/api/platform`. Session and household come from shared context. Viewer mutations return 403; unknown household records return 404. Money is serialized as decimal strings. All services are local simulations, never external actions. Object creation returns the saved object; list and workspace GETs below return objects with named arrays.

## Credit

`GET /credit` → `{accounts:[{id,name,currency,balance,credit_limit,apr_pct,minimum_payment,evidence}], report:{score:724,scale_min:300,scale_max:850,history:[{as_of,score}],factors:[{code:"payment_history",impact:"positive"},{code:"credit_utilization",impact:"mixed"}],evidence}, utilization:[{currency,balance,credit_limit,utilization_pct,evidence}]}`. Empty households have report null, accounts/utilization empty.

`POST /credit/accounts` body `{ "name":"Travel card", "currency":"USD", "balance":"1200", "credit_limit":"5000", "apr_pct":"18", "minimum_payment":"60", "as_of":"2026-09-20" }` → saved account. `PUT /credit/accounts/{id}` accepts the same complete body.

`POST /credit/payoff` body `{ "account_id":"credit-demo", "extra_monthly_payment":"50" }` → `{account_id,currency,monthly_payment,status,months,total_interest,total_paid,formula,assumptions,evidence}`. Status is `paid_off`, `non_amortizing`, or `horizon_exceeded`; months is null when unresolved. Monthly interest is balance × APR / 1200, rounded half up to currency precision, fixed payment capped to amount owed, horizon 1200 months, no fees/new borrowing/rate changes.

## Tax organizer

`GET /tax` → `{organizers:[{id,country,year,currency,status,recorded_at}],items:[{id,organizer_id,kind,title,amount,effective_on,completed,recorded_at}]}`.

`POST /tax/organizers` body `{ "country":"DO", "year":2026, "currency":"DOP" }` → organizer. Unique per household/country/year/currency, repeated create returns existing.

`POST /tax/items` body `{ "organizer_id":"tax-demo", "kind":"income", "title":"Consulting", "amount":"25000", "effective_on":"2026-09-20" }` → item. Kinds: `income`, `expense`, `document`, `checklist`; money required only for income/expense. `PATCH /tax/items/{id}` body `{ "completed":true }` → item. `PATCH /tax/organizers/{id}` body `{ "status":"complete" }` → organizer; checklist and document items must be complete. `open` reopens.

`POST /tax/scenario` body `{ "organizer_id":"tax-demo", "user_rate_pct":"15" }` → `{income,expenses,net_amount,user_rate_pct,scenario_amount,currency,formula,legal_status:"worksheet_only",evidence,source_records:[{id,effective_on,recorded_at,kind}],rate_evidence}`. This is net recorded income × the user's explicit rate, not a national tax calculation. Calculated `evidence.inputs` identifies the organizer and financial items; `as_of` is their oldest effective date (calculation date if empty). `source_records` preserves each financial item's effective date, recording timestamp, and `user` or `synthetic` origin. `rate_evidence` labels the explicitly supplied rate as a user input recorded for this request. All publication dates remain null.

`GET /tax/organizers/{id}/export?format=json` downloads `{legal_status:"worksheet_only",organizer,items}`. `format=csv` downloads worksheet CSV.

## Estate inventory

`GET /estate` → `{assets:[],contacts:[],beneficiaries:[],documents:[],checklist:[],legal_status:"inventory_only_no_legal_validity"}`.

`POST /estate/assets` body `{ "name":"Savings account", "currency":"USD", "value":"4000", "as_of":"2026-09-20" }` → asset.

`POST /estate/contacts` body `{ "name":"Alex Rivera", "relationship":"Sibling", "email":"alex@example.test" }` → contact.

`PUT /estate/assets/{id}/beneficiaries` body `{ "shares":[{"contact_id":"contact-demo","share_pct":"100"}] }` → `{id,asset_id,shares,allocated_pct,recorded_at}`. Replaces shares atomically; total at most 100%, no duplicate contacts, all records household scoped.

`POST /estate/documents` body `{ "title":"Policy record", "location":"Home safe", "effective_on":"2026-09-20" }` → document location, no file upload.

`POST /estate/checklist` body `{ "title":"Review inventory" }` → checklist item. `PATCH /estate/checklist/{id}` body `{ "completed":true }` → item. `GET /estate/export?format=json` or `csv` downloads inventory labelled no legal validity.

## Human help

`GET /appointments` → `{specialists:[{id,name,specialty,demo:true}],slots:[{id,specialist_id,starts_at,ends_at,available}],reservations:[{id,slot_id,status,recorded_at}],mode:"local_demo"}`.

`POST /appointments` body `{ "slot_id":"slot-demo-20260921T1400", "request_key":"client-generated-unique-key" }` → reservation. Request-key retries return the original reservation; conflicting payload is 409. Only one active reservation per slot globally. Always select IDs from the returned catalog. Initialization and catalog reads ensure two future slots per day for the next six UTC days. Expired unreferenced slots are removed; slots referenced by current or historical reservations remain unchanged.

`PATCH /appointments/{id}` body `{ "slot_id":"slot-demo-20260921T1500" }` → rescheduled reservation. `POST /appointments/{id}/cancel` with no body → cancelled reservation, idempotent. `GET /appointments/{id}/calendar` downloads `.ics` labelled local demo, without invitations or contacts.

## Membership and employer

`GET /membership` → `{plans:[{id:"monthly",amount:"9",currency:"USD",interval:"month",evidence},{id:"annual",amount:"90",currency:"USD",interval:"year",evidence}],membership:null|{plan_id,status,recorded_at},receipts:[{id,plan_id,amount,currency,status:"simulated_no_charge",recorded_at}],mode:"local_demo"}`.

`POST /membership` body `{ "plan_id":"monthly", "request_key":"client-generated-unique-key" }` → `{membership,receipt}`; idempotent, no charges. Replaying an old request key returns its historical membership/receipt response; `GET /membership` remains the current state even after later plan changes or cancellation. `POST /membership/cancel` → `{membership}` with cancelled status, idempotent.

`GET /employer` → `{enrollment:null|{employer_id,benefit_id,status:"enrolled"|"left",recorded_at},demo_code:"CLARA-DEMO",benefits:[{id,title}],mode:"local_demo"}`. `POST /employer/enroll` body `{ "code":"CLARA-DEMO" }` → enrollment. `PUT /employer/benefit` body `{ "benefit_id":"learning" }` → enrollment; IDs `learning`, `wellness`, `planning`. `POST /employer/leave` → `{enrollment}`.

Error payload shaping uses the shared PlatformError handler. User records carry effective/as-of and recording dates; seeded report and catalog evidence are synthetic, not official reports, rates, bookings, filing, or legal services. CSV string cells that could execute spreadsheet formulas are prefixed with an apostrophe.

Service subscriptions persist in `p_service_memberships`, separate from identity household-role membership authority. Service export/reset/usage callbacks operate only on service-owned tables.
