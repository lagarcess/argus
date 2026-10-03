# Cuadrao Terms of Use and Privacy Policy (draft)

**Status:** Draft. Do not publish. This replaces the
[archived Argus version](archive/2026-08-07-argus-terms-privacy.md) only once
in-app account deletion is live. It lands with the deletion work, not before,
because it promises behavior the app doesn't have yet.

**Sources:** [decision log](../specs/argus-decision-log.md) (Oct 1 Household
policy, Oct 2 lane locks), [ingestion connectors](../specs/lanes/financial-ingestion-connectors.md)
(disconnect and retention), [ARCHITECTURE](../ARCHITECTURE.md) (providers).
This is product copy written to match those docs. It is not legal advice.

**Pending (do not publish while any of these is open):**

| # | Open item | Owner |
| --- | --- | --- |
| P1 | Sign in with Apple is connected, and deletion cancels it. Needs Lucas's Apple sign-in key. | Lucas, then eng |
| P2 | If the household admin deletes their account, the role passes to the longest-standing member, or the household closes if nobody is left. | Lucas to lock |
| P3 | When an owner deletes their account, the household's locked copy of their history is deleted too, and members see a short note. | Lucas to lock |
| P4 | Operating entity, country and governing law. | Lucas (Iris drafts) |
| P5 | Cuadrao support address. Only the get-argus.com one exists today. | Lucas |
| P6 | Where these are published (likely cuadrao.ai, which the App Store listing needs) and what happens to the web app's cookie section. | Yelena |
| P7 | How long backups and operational logs keep deleted data. | Eng to state from the real setup; don't guess |
| P8 | Whether counsel reviews before beta. | Lucas |

Bracketed **[Pendiente Pn]** marks show where each open item lands in the text.
Spanish is the primary version; English follows and must say the same thing.

---

## Español

_Fecha de entrada en vigor: [al publicarse]_

### Términos de uso

Cuadrao es una app de finanzas personales y del hogar en beta privada. Te ayuda
a registrar tus cuentas, movimientos, planes y deudas, y a hacer cálculos y
preguntas sobre tu dinero. Estos términos describen cómo funciona hoy y van a
cambiar conforme cambie el producto.

**No es asesoría financiera.** Cuadrao ofrece herramientas y cálculos
informativos. No ofrece asesoría financiera, de inversión, legal, fiscal ni
contable. Los cálculos son estimados según los datos que tú registras o
conectas. Tú decides qué hacer con tu dinero.

**No es un banco.** Cuadrao no es un banco, una entidad de intermediación
financiera ni un asesor. No guarda fondos, no mueve dinero, no paga facturas y
no ejecuta operaciones. Cuando conectas una fuente, Cuadrao solo lee la
información que tú autorizas.

**Beta privada.** Cuadrao se ofrece tal cual, sin garantías. Se entra con un
código de invitación. Las funciones pueden cambiar, fallar o eliminarse sin
aviso. Podemos limitar el acceso, suspender cuentas o retirar contenido que
genere riesgos de seguridad, abuso u operación.

**Elegibilidad.** Debes tener edad suficiente para celebrar un acuerdo
vinculante donde vives. No uses Cuadrao en nombre de otra persona sin su
autorización.

**Hogares.** Puedes crear un hogar e invitar a otras personas. Una invitación
solo te hace miembro: no comparte tus cuentas por sí sola. Cada dueño decide qué
cuenta comparte y si los demás solo la ven o también la editan. Quien crea el
hogar administra las invitaciones y los miembros. Si sales o te sacan de un
hogar, pierdes el acceso a sus cuentas compartidas de inmediato.

**Uso aceptable.** No uses Cuadrao para infringir la ley, abusar del servicio,
acceder a cuentas que no son tuyas, aplicar ingeniería inversa a sistemas
privados ni presentar sus resultados como asesoría profesional.

**Servicios de terceros.** Cuadrao depende de proveedores para alojamiento,
inicio de sesión, conexiones financieras, modelos de IA, voz, notificaciones y
protección contra bots. Se detallan en la política de privacidad.

**Eliminar tu cuenta.** Puedes eliminar tu cuenta desde la app. Después de una
pantalla de confirmación, la eliminación es definitiva. La política de
privacidad explica qué se borra y qué se conserva.

**Ley aplicable.** [Pendiente P4]

**Contacto.** [Pendiente P5]

### Política de privacidad

Esta política explica qué datos maneja Cuadrao, para qué, con quién se
comparten y qué puedes controlar.

**Datos que recopilamos**

- Tu cuenta: correo, nombre si lo das, idioma y estado de inicio de sesión.
  [Pendiente P1: inicio de sesión con Apple]
- Lo que registras: cuentas, saldos, movimientos, facturas, deudas, metas,
  presupuestos, bienes y espacios.
- Lo que importas: documentos y recibos que subes, y los datos que traen las
  fuentes que conectas.
- Tus conversaciones con Cuadrao, incluida la voz cuando la usas.
- Datos del hogar: miembros, invitaciones y qué cuentas compartiste con quién.
- Invitaciones: quién envió cada código y si se aceptó.
- Comentarios, solicitudes de soporte, datos básicos del dispositivo, eventos de
  uso, registros y diagnósticos de errores.

**Fuentes que tú conectas.** Solo se activan si tú las conectas, y puedes
desconectarlas cuando quieras.

- **Gmail:** acceso de solo lectura para encontrar alertas, estados de cuenta y
  avisos de vencimiento de tus bancos. Guardamos los datos extraídos, un
  fragmento corto y referencias a los adjuntos, nunca el correo completo.
- **Plaid:** cuentas de bancos y tarjetas fuera de República Dominicana que
  Plaid admite.
- **Atajos de Apple:** capturas que tú configuras y ejecutas en tu iPhone.

Al desconectar una fuente, le pedimos al proveedor que revoque el acceso y
borramos las credenciales guardadas y los borradores que no revisaste. Los
movimientos que confirmaste siguen siendo tuyos, con un registro mínimo de su
origen. Si el proveedor no confirma la revocación, te lo decimos para que la
revoques allí también. Las credenciales se guardan cifradas.

**Cómo usamos los datos.** Para operar la app, iniciar tu sesión, guardar tu
información financiera, hacer cálculos, responder tus preguntas, leer los
documentos que subes, enviarte recordatorios, proteger el servicio, responder
soporte y mejorar Cuadrao.

**Proveedores**

- Supabase: inicio de sesión y base de datos.
- Render: alojamiento del servidor.
- OpenRouter y sus proveedores de modelos: interpretar tus preguntas y leer
  documentos.
- xAI: voz, cuando la usas.
- Plaid y Google: solo si conectas esas fuentes.
- Servicio de notificaciones de Apple: solo si activas las notificaciones.
  Las notificaciones nunca muestran montos.
- PostHog: analítica de producto en nuestros servidores, solo cuando está
  activada.
- Cloudflare: entrega del dominio y protección contra bots.

**Lo que ven los demás en un hogar.** Ser miembro no expone tus cuentas,
documentos, conversaciones ni ingresos privados. Los demás solo ven las cuentas
que tú compartes. Si sales del hogar, tus cuentas se van contigo. Los miembros
que tenían acceso conservan el historial hasta ese día, en gris y solo lectura.

**Acceso y retención.** El acceso del equipo a tus datos se limita a operar,
depurar, proteger y mejorar Cuadrao. Conservamos tus datos mientras tu cuenta
esté activa. [Pendiente P7]

**Tus controles**

- Editar o borrar lo que registras, y archivar o borrar conversaciones.
- Elegir qué cuentas compartes con tu hogar y retirarlas.
- Desconectar cualquier fuente conectada.
- Activar o desactivar las notificaciones.
- Eliminar tu cuenta desde la app.

**Al eliminar tu cuenta** borramos tu perfil, tus cuentas, movimientos,
documentos, conversaciones, planes y fuentes conectadas, y revocamos esas
conexiones. Solo conservamos un registro anónimo de que se envió y se aceptó
una invitación, sin tu nombre ni ningún identificador.
[Pendiente P1: también se cancela tu inicio de sesión con Apple]
[Pendiente P2: si administrabas un hogar]
[Pendiente P3: el historial que el hogar conservaba de tus cuentas]

**Venta de información.** Cuadrao no vende ni comparte tu información personal
y no la usa para publicidad dirigida. Si eso cambia, esta política se
actualizará antes.

**Contacto.** [Pendiente P5]

---

## English

_Effective date: [on publication]_

### Terms of Use

Cuadrao is a personal and household finance app in private beta. It helps you
record your accounts, activity, plans and debts, and do calculations and ask
questions about your money. These terms describe how it works today and will
change as the product does.

**Not financial advice.** Cuadrao provides informational tools and
calculations. It does not provide financial, investment, legal, tax or
accounting advice. Calculations are estimates based on the data you record or
connect. You decide what to do with your money.

**Not a bank.** Cuadrao is not a bank, financial intermediary or adviser. It
does not hold funds, move money, pay bills or execute transactions. When you
connect a source, Cuadrao only reads the information you authorize.

**Private beta.** Cuadrao is provided as is, without warranties. Access is by
invite code. Features may change, break or be removed without notice. We may
limit access, suspend accounts or remove content that creates security, abuse
or operational risk.

**Eligibility.** You must be old enough to form a binding agreement where you
live. Don't use Cuadrao on someone else's behalf without their authorization.

**Households.** You can create a household and invite others. An invitation
only makes someone a member; it doesn't share your accounts on its own. Each
owner decides which accounts to share and whether others can only view or also
edit. The household creator manages invitations and members. If you leave or
are removed, you lose access to its shared accounts right away.

**Acceptable use.** Don't use Cuadrao to break the law, abuse the service,
access accounts that aren't yours, reverse engineer private systems, or present
its output as professional advice.

**Third-party services.** Cuadrao relies on providers for hosting, sign-in,
financial connections, AI models, voice, notifications and bot protection. The
privacy policy lists them.

**Deleting your account.** You can delete your account in the app. After one
confirmation screen, deletion is final. The privacy policy explains what is
deleted and what is kept.

**Governing law.** [Pending P4]

**Contact.** [Pending P5]

### Privacy Policy

This policy explains what data Cuadrao handles, why, who it's shared with, and
what you control.

**Data we collect**

- Your account: email, name if you give it, language and sign-in state.
  [Pending P1: Sign in with Apple]
- What you record: accounts, balances, activity, bills, debts, goals, budgets,
  assets and spaces.
- What you import: documents and receipts you upload, and data from sources you
  connect.
- Your conversations with Cuadrao, including voice when you use it.
- Household data: members, invitations, and which accounts you shared with whom.
- Invitations: who sent each code and whether it was accepted.
- Feedback, support requests, basic device details, usage events, logs and
  error diagnostics.

**Sources you connect.** These are only on if you connect them, and you can
disconnect them anytime.

- **Gmail:** read-only access to find alerts, statements and due-date notices
  from your banks. We keep the extracted fields, a short excerpt and attachment
  references, never the full email.
- **Plaid:** bank and card accounts outside the Dominican Republic that Plaid
  supports.
- **Apple Shortcuts:** captures you set up and run on your iPhone.

When you disconnect a source, we ask the provider to revoke access and delete
the stored credentials and any drafts you hadn't reviewed. Activity you
confirmed stays yours, with a minimal record of where it came from. If the
provider doesn't confirm revocation, we tell you so you can revoke it there too.
Credentials are stored encrypted.

**How we use data.** To run the app, sign you in, save your financial
information, do calculations, answer your questions, read documents you upload,
send reminders, protect the service, respond to support and improve Cuadrao.

**Providers**

- Supabase: sign-in and database.
- Render: server hosting.
- OpenRouter and its model providers: interpreting your questions and reading
  documents.
- xAI: voice, when you use it.
- Plaid and Google: only if you connect those sources.
- Apple Push Notification service: only if you turn notifications on.
  Notifications never show amounts.
- PostHog: product analytics on our servers, only when enabled.
- Cloudflare: domain delivery and bot protection.

**What others see in a household.** Being a member doesn't expose your private
accounts, documents, conversations or income. Others only see accounts you
share. If you leave the household, your accounts go with you. Members who had
access keep the history up to that day, greyed out and read-only.

**Access and retention.** Team access to your data is limited to operating,
debugging, securing and improving Cuadrao. We keep your data while your account
is active. [Pending P7]

**Your controls**

- Edit or delete what you record, and archive or delete conversations.
- Choose which accounts you share with your household, and stop sharing them.
- Disconnect any connected source.
- Turn notifications on or off.
- Delete your account in the app.

**When you delete your account**, we delete your profile, accounts, activity,
documents, conversations, plans and connected sources, and revoke those
connections. The only thing we keep is an anonymous record that an invitation
was sent and accepted, with no name or identifier.
[Pending P1: your Sign in with Apple is also revoked]
[Pending P2: if you administered a household]
[Pending P3: the history a household kept of your accounts]

**Sale of information.** Cuadrao does not sell or share your personal
information and does not use it for targeted advertising. If that changes, this
policy will be updated first.

**Contact.** [Pending P5]
