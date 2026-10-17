import type { StrategyConfirmationPayload } from "@/components/chat/types";

export const PREVIEW_VIEWS = ["home", "accounts", "argus", "plan", "search", "updates", "settings"] as const;
export type PreviewView = (typeof PREVIEW_VIEWS)[number];
export const PREVIEW_STATES = ["sample", "empty", "loading", "error"] as const;
export type PreviewState = (typeof PREVIEW_STATES)[number];
export type PreviewAudience = "guest" | "sample";

export function previewLocation(params: { get: (name: string) => string | null }) {
  const candidateView = params.get("view");
  const candidateState = params.get("state");
  const view = PREVIEW_VIEWS.find((item) => item === candidateView) ?? "argus";
  const state = PREVIEW_STATES.find((item) => item === candidateState) ?? "sample";
  const audience = params.get("audience") === "sample" ? "sample" as const : "guest" as const;
  const account: string | undefined = audience === "sample" && state === "sample" && (view === "accounts" || view === "search")
    ? SAMPLE.accounts.find((item) => item.id === params.get("account"))?.id : undefined;
  return {
    view, state, audience, ...(account ? { account } : {}),
  };
}

export function previewHref(location: ReturnType<typeof previewLocation>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(location)) if (value !== undefined) params.set(key, value);
  return `/dev/ecosystem?${params.toString()}`;
}

const en = {
  home: "Home", accounts: "Accounts", argus: "Argus", plan: "Plan", search: "Search", updates: "Updates", settings: "Settings",
  primaryNav: "Primary navigation", skip: "Skip to content", preview: "Ecosystem preview", previewControls: "Preview controls",
  expandNavigation: "Expand navigation", collapseNavigation: "Collapse navigation", closeAccountDetails: "Close account details",
  previewNote: "Fictional data. No model calls or financial records are saved.", controlsNote: "These controls change the demonstration only. Sample workspace does not sign you in.",
  destination: "Destination", audience: "Audience", state: "State", guest: "Guest view", sampleWorkspace: "Sample workspace",
  sample: "Sample populated", empty: "Empty", loading: "Loading", error: "Error", sampleLabel: "Sample", localOnly: "Local preview",
  personal: "Personal", household: "Household", spaces: "Financial context", contextNote: "Personal and shared information have separate boundaries. Household sharing is not connected in this preview.",
  record: "Record activity", addAccount: "Add account", manage: "Manage", viewAll: "View all", close: "Close", back: "Back", done: "Done", cancel: "Cancel", continue: "Continue",
  registration: "Create an account to continue", registrationBody: "The ecosystem requires registration before recording or managing financial information. This preview cannot register you or return you to a completed action.",
  registrationNote: "These links leave the preview and open the existing Argus experience.", createAccount: "Create account", signIn: "Sign in", existingChat: "Open existing chat", leavePreview: "Leave preview",
  limitedTitle: "A preview of this step", limitedBody: "This layout is here to review. It does not create, edit, send or save anything outside this page.", dismiss: "Got it",
  loadingTitle: "Loading layout", loadingBody: "A selected preview state. No account information is being requested.",
  errorTitle: "Let’s try that again", errorBody: "This is a sample error. Your preview draft is still here, and no request failed.", retry: "Show sample again",
  recordedPosition: "Recorded position", recordedBasis: "Based on the balances in this sample, not a complete financial picture.", recordedAsOf: "Sample records · Sep 28, 2026",
  cashAndBank: "Cash & bank accounts", youOwe: "You owe", separateCurrencies: "Currencies stay separate", usdBasis: "One USD account. No exchange rate or combined total.",
  unknownBalance: "Balance unknown", unknownBasis: "One account has no balance. It is excluded from recorded totals.",
  comingUp: "Coming up", comingUpNote: "Planned, not yet recorded", creditPayment: "Credit card payment", rent: "Rent", expectedIncome: "Expected income", expectedNote: "Expected income is not part of your current balance.",
  sep30: "Sep 30", oct01: "Oct 1", oct05: "Oct 5", recentActivity: "Recent activity", recorded: "Recorded", planned: "Planned", today: "Sep 28, 2026",
  grocery: "Groceries", receivedIncome: "Commission received", cashTransfer: "Transfer to cash", yesterday: "Sep 27", activityNote: "Sample entries. Transfers are shown separately from spending.",
  accountIntro: "A place for the money you have, and what you owe.", accountCount: "Sample accounts", accountCoverage: "Start with what you know", accountCoverageBody: "Cash counts. Missing balances stay unknown. You can add more detail after opening an account.",
  everyday: "Everyday spending", pocket: "Pocket money", safety: "Safety net", card: "My credit card", dollars: "Dollar savings", unknownAccount: "An account to finish later",
  cash: "Cash", checking: "Checking", savings: "Savings", investments: "Investments", credit: "Credit card", debt: "Other debt",
  asOf: "As of Sep 28", owed: "owed", individual: "Individual", private: "Private to you", samplePrivacy: "Sample ownership label. No sharing or permissions are implemented.",
  source: "Source", manualSource: "Manual sample", currency: "Currency", balance: "Recorded balance", activity: "Activity", noActivity: "No activity yet", openingBalance: "Opening balance is separate from activity.",
  editDetails: "Edit details", checkBalance: "Check balance", accountDetails: "Account details", type: "Account type", chooseType: "What would you like to add?", change: "Change",
  dopCurrency: "DOP · Dominican peso", usdCurrency: "USD · US dollar",
  createTitle: "Add to your picture", createIntro: "Start with what you know.", nickname: "Nickname (optional)", startingBalance: "Starting balance (optional)", leaveBlank: "Leave blank if you don’t know. Blank never means zero.",
  invalidBalance: "Enter a number such as 1,250.50, or leave it blank if unknown.",
  draftOnly: "Unsaved preview draft. Use fictional information.", reviewDraft: "Review draft", draftTitle: "Review your account draft", draftNotice: "No financial record has been created. This draft does not change the sample accounts.",
  returnDraft: "Return to draft", notProvided: "Not provided", unnamed: "Unnamed account", moreDetails: "More details", institution: "Institution (optional)", reference: "Account reference (optional)",
  correctionTitle: "Review the difference", checkedOn: "Checked on", previousBalance: "Balance before check", observedBalance: "Balance you checked", difference: "Difference", correctionBasis: "Basis: observed balance supplied for this fixed example.",
  discrepancy: "This difference is unexplained. A balance adjustment is different from recording missing activity; it should not invent income or spending.", incompleteHistory: "A balance check does not prove transaction history is complete.",
  previewAdjustment: "Preview adjustment", missingActivity: "Review missing activity", adjustmentTitle: "Balance adjustment draft", adjustmentNotice: "Nothing has been posted. The sample balance remains unchanged.",
  notes: "Note (optional)", noteLimit: "Up to 200 characters. Fictional information only.",
  homeEmpty: "Your picture starts with one account", homeEmptyBody: "Add cash, a bank account or a debt when you’re ready. Unknown balances can wait.",
  accountsEmpty: "Start with what you know", accountsEmptyBody: "A little cash, one bank balance, or an amount you owe is enough to begin.",
  planIntro: "Give your next steps a place.", overview: "Overview", goals: "Goals", budgets: "Budgets", debts: "Debts", planTabs: "Plan sections",
  until: "Through Oct 15, 2026", commitments: "Upcoming commitments", planBasis: "What this plan includes", planBasisBody: "Recorded balances, planned payments and expected income remain distinct. This preview does not calculate money left to spend.",
  projection: "Your outlook, with its assumptions", projectionBody: "A future projection belongs here once its dates, inputs and calculation are connected. No projected balance is calculated in this preview.",
  newPlan: "Add a plan", goalTitle: "Emergency cushion", goalBody: "A little more breathing room", goalRecorded: "Recorded toward goal", goalTarget: "Goal amount", budgetTitle: "Everyday essentials", budgetBody: "Groceries, transport and daily needs", budgetRecorded: "Sample spending", budgetLimit: "Planned limit", debtTitle: "Credit card", debtBody: "Keep the next payment in view", balanceOwed: "Recorded amount owed", nextPayment: "Planned payment",
  goalCaveat: "A goal is an intention. It does not reserve money or move it out of an account.", budgetCaveat: "A budget is a view of spending. It does not move money or subtract it a second time.",
  planEmpty: "Room for your next step", planEmptyBody: "Bring a goal, a budget or a payment into the same picture.",
  searchTitle: "Pick up where you left off", searchPlaceholder: "Search sample accounts, activity and conversations", searchLabel: "Search sample records", all: "All", conversations: "Conversations", plans: "Plans", searchCategories: "Search categories", sampleResults: "Local sample results", noResults: "No sample results", noResultsBody: "Try another word or clear your filters.", clearSearch: "Clear search", clearFilter: "Clear account filter",
  searchEmpty: "Your records will be easier to find here", searchEmptyBody: "Accounts, activity, plans and conversations will keep their original context.",
  updateIntro: "Changes worth a closer look.", updateBalance: "A balance needs a check", updateBalanceBody: "The example observed balance differs from the recorded balance. Review its basis before any correction.",
  updatePayment: "A payment is coming up", updatePaymentBody: "Your sample credit card plan has a payment on September 30. It has not been recorded as paid.", updateImport: "A statement needs review", updateImportBody: "A sample import contains an uncertain entry. Review it before it could become part of your picture.",
  review: "Review", openPlan: "Open plan", updatesEmpty: "You’re all caught up in this sample", updatesEmptyBody: "Relevant changes would appear here with their source and a clear next step.",
  settingsIntro: "Make Argus feel like yours.", personalDetails: "Personal details", personalDetailsBody: "Name, photo and profile information", app: "App", account: "Account", support: "Support", preferences: "Preferences", preferencesBody: "Appearance and language", appearance: "Appearance", appearanceBody: "Light, Dark or System", language: "Language", languageBody: "English or Español (Latinoamérica)", browserPreferences: "Appearance and language use the existing browser preferences. No account profile is updated.",
  personalization: "Personalization", personalizationBody: "How Argus works with your context", security: "Security", securityBody: "Sign-in and account protection", dataPrivacy: "Data & privacy", usage: "Usage", usageBody: "Your activity and allowances",
  notifications: "Notifications", notificationsBody: "Choose the updates you hear about", dataControls: "Data controls", dataControlsBody: "Your records and privacy", archivedChats: "Archived conversations", archivedBody: "Return to past conversations", help: "Help & feedback", helpBody: "Find help and share your thoughts", about: "About Argus", aboutBody: "A clearer picture of your money", profileSample: "Preview identity only. You are not signed in through this page.",
  recents: "Recents", newChat: "New chat", temporary: "Temporary", temporaryTitle: "Temporary chat preview", temporaryBody: "This demonstrates where temporary-chat controls belong. It does not activate a privacy mode, change retention or grant access to personal context.", temporaryContext: "Use of personal context needs a separate, verified permission contract.",
  searchRecents: "Search sample conversations", recentMoney: "Making room for an emergency fund", recentMarket: "Understanding market cycles", recentInvest: "A monthly investing idea", recentSample: "Read-only sample conversation", recentsEmpty: "No sample conversations here", recentsNoResults: "No sample conversations match", searchDraftNote: "Start a new chat with this search as an editable, unsent draft.", newChatNote: "The new-chat layout is ready. Your unsent draft stays in the composer.",
  composerLabel: "Unsent preview message", composerPlaceholder: "Ask anything about money…", composerHint: "Preview composer. Nothing is sent.", send: "Send preview message", sendNotice: "Your draft has not been sent. This preview makes no model calls. Open existing chat to ask Argus.", attach: "Add attachment", voice: "Voice input", suggestions: "Things to explore", chipMoney: "Understand a money choice", chipMarket: "Explore markets", chipAccounts: "Make sense of my accounts", sampleConversationBody: "This is a fixed layout example. The existing Argus chat owns real conversations, calculations, research and historical tests.",
  artifactTitle: "Existing confirmation presentation", artifactNote: "Read-only sample. No test can be launched from this card.",
  backSettings: "Back to settings", backPreferences: "Back to preferences", backAccount: "Back to account", noSave: "Nothing was saved", stateApplies: "State controls affect the current destination; preferences remain available.",
} as const;

export type CopyKey = keyof typeof en;
export type PreviewCopy = Record<CopyKey, string>;

const es: PreviewCopy = {
  home: "Inicio", accounts: "Cuentas", argus: "Argus", plan: "Plan", search: "Buscar", updates: "Novedades", settings: "Configuración",
  primaryNav: "Navegación principal", skip: "Ir al contenido", preview: "Vista previa del ecosistema", previewControls: "Controles de vista previa",
  expandNavigation: "Expandir navegación", collapseNavigation: "Contraer navegación", closeAccountDetails: "Cerrar detalles de la cuenta",
  previewNote: "Datos ficticios. No se llama a modelos ni se guardan registros financieros.", controlsNote: "Estos controles solo cambian la demostración. El espacio de ejemplo no inicia sesión.",
  destination: "Destino", audience: "Público", state: "Estado", guest: "Vista de visitante", sampleWorkspace: "Espacio de ejemplo",
  sample: "Con ejemplos", empty: "Vacío", loading: "Cargando", error: "Error", sampleLabel: "Ejemplo", localOnly: "Vista previa local",
  personal: "Personal", household: "Hogar", spaces: "Contexto financiero", contextNote: "La información personal y compartida tiene límites distintos. Compartir con el hogar no está conectado en esta vista previa.",
  record: "Registrar actividad", addAccount: "Agregar cuenta", manage: "Administrar", viewAll: "Ver todo", close: "Cerrar", back: "Volver", done: "Listo", cancel: "Cancelar", continue: "Continuar",
  registration: "Crea una cuenta para continuar", registrationBody: "Debes registrarte antes de registrar o administrar información financiera. Esta vista previa no puede registrarte ni devolverte a una acción completada.",
  registrationNote: "Estos enlaces salen de la vista previa y abren la experiencia actual de Argus.", createAccount: "Crear cuenta", signIn: "Iniciar sesión", existingChat: "Abrir chat actual", leavePreview: "Salir de la vista previa",
  limitedTitle: "Una vista previa de este paso", limitedBody: "Este diseño está aquí para revisarlo. No crea, edita, envía ni guarda nada fuera de esta página.", dismiss: "Entendido",
  loadingTitle: "Diseño de carga", loadingBody: "Es un estado de ejemplo seleccionado. No se está solicitando información de cuentas.",
  errorTitle: "Intentémoslo de nuevo", errorBody: "Este error es un ejemplo. Tu borrador sigue aquí y no ha fallado ninguna solicitud.", retry: "Volver al ejemplo",
  recordedPosition: "Posición registrada", recordedBasis: "Según los saldos de este ejemplo; no es una imagen financiera completa.", recordedAsOf: "Registros de ejemplo · 28 sep 2026",
  cashAndBank: "Efectivo y cuentas bancarias", youOwe: "Lo que debes", separateCurrencies: "Cada moneda por separado", usdBasis: "Una cuenta en USD. Sin tasa de cambio ni total combinado.",
  unknownBalance: "Saldo desconocido", unknownBasis: "Una cuenta no tiene saldo. No se incluye en los totales registrados.",
  comingUp: "Próximamente", comingUpNote: "Planificado, aún no registrado", creditPayment: "Pago de tarjeta", rent: "Alquiler", expectedIncome: "Ingreso esperado", expectedNote: "Los ingresos esperados no forman parte de tu saldo actual.",
  sep30: "30 sep", oct01: "1 oct", oct05: "5 oct", recentActivity: "Actividad reciente", recorded: "Registrado", planned: "Planificado", today: "28 sep 2026",
  grocery: "Supermercado", receivedIncome: "Comisión recibida", cashTransfer: "Transferencia a efectivo", yesterday: "27 sep", activityNote: "Movimientos de ejemplo. Las transferencias se muestran aparte de los gastos.",
  accountIntro: "Un lugar para el dinero que tienes y lo que debes.", accountCount: "Cuentas de ejemplo", accountCoverage: "Empieza con lo que sabes", accountCoverageBody: "El efectivo cuenta. Los saldos que faltan siguen siendo desconocidos. Puedes agregar detalles después de abrir una cuenta.",
  everyday: "Gastos del día a día", pocket: "Dinero de bolsillo", safety: "Fondo de respaldo", card: "Mi tarjeta de crédito", dollars: "Ahorros en dólares", unknownAccount: "Una cuenta para completar después",
  cash: "Efectivo", checking: "Cuenta corriente", savings: "Ahorros", investments: "Inversiones", credit: "Tarjeta de crédito", debt: "Otra deuda",
  asOf: "Al 28 sep", owed: "por pagar", individual: "Individual", private: "Privado para ti", samplePrivacy: "Etiqueta de propiedad de ejemplo. No se han implementado permisos ni uso compartido.",
  source: "Fuente", manualSource: "Ejemplo manual", currency: "Moneda", balance: "Saldo registrado", activity: "Actividad", noActivity: "Aún no hay actividad", openingBalance: "El saldo inicial se muestra aparte de los movimientos.",
  editDetails: "Editar detalles", checkBalance: "Comprobar saldo", accountDetails: "Detalles de la cuenta", type: "Tipo de cuenta", chooseType: "¿Qué te gustaría agregar?", change: "Cambiar",
  dopCurrency: "DOP · Peso dominicano", usdCurrency: "USD · Dólar estadounidense",
  createTitle: "Agrega a tu panorama", createIntro: "Empieza con lo que sabes.", nickname: "Nombre (opcional)", startingBalance: "Saldo inicial (opcional)", leaveBlank: "Déjalo vacío si no lo sabes. Vacío nunca significa cero.",
  invalidBalance: "Escribe un número como 1,250.50, o déjalo vacío si no lo sabes.",
  draftOnly: "Borrador sin guardar. Usa información ficticia.", reviewDraft: "Revisar borrador", draftTitle: "Revisa el borrador de tu cuenta", draftNotice: "No se ha creado ningún registro financiero. Este borrador no cambia las cuentas de ejemplo.",
  returnDraft: "Volver al borrador", notProvided: "Sin indicar", unnamed: "Cuenta sin nombre", moreDetails: "Más detalles", institution: "Institución (opcional)", reference: "Referencia de cuenta (opcional)",
  correctionTitle: "Revisa la diferencia", checkedOn: "Fecha de comprobación", previousBalance: "Saldo antes de comprobar", observedBalance: "Saldo que comprobaste", difference: "Diferencia", correctionBasis: "Base: saldo observado aportado para este ejemplo fijo.",
  discrepancy: "Esta diferencia aún no tiene explicación. Un ajuste de saldo es distinto de registrar movimientos faltantes; no debe inventar ingresos ni gastos.", incompleteHistory: "Comprobar un saldo no demuestra que el historial esté completo.",
  previewAdjustment: "Ver borrador del ajuste", missingActivity: "Revisar actividad faltante", adjustmentTitle: "Borrador del ajuste de saldo", adjustmentNotice: "No se ha registrado nada. El saldo de ejemplo sigue igual.",
  notes: "Nota (opcional)", noteLimit: "Hasta 200 caracteres. Solo información ficticia.",
  homeEmpty: "Tu panorama empieza con una cuenta", homeEmptyBody: "Agrega efectivo, una cuenta bancaria o una deuda cuando quieras. Los saldos desconocidos pueden esperar.",
  accountsEmpty: "Empieza con lo que sabes", accountsEmptyBody: "Algo de efectivo, un saldo bancario o una deuda es suficiente para comenzar.",
  planIntro: "Dale un lugar a tus próximos pasos.", overview: "Resumen", goals: "Metas", budgets: "Presupuestos", debts: "Deudas", planTabs: "Secciones del plan",
  until: "Hasta el 15 oct 2026", commitments: "Compromisos próximos", planBasis: "Qué incluye este plan", planBasisBody: "Los saldos registrados, pagos planificados e ingresos esperados se mantienen separados. Esta vista previa no calcula cuánto queda para gastar.",
  projection: "Tu perspectiva, con sus supuestos", projectionBody: "Aquí irá una proyección cuando sus fechas, datos y cálculo estén conectados. Esta vista previa no calcula un saldo proyectado.",
  newPlan: "Agregar un plan", goalTitle: "Colchón de emergencia", goalBody: "Un poco más de tranquilidad", goalRecorded: "Registrado para la meta", goalTarget: "Monto de la meta", budgetTitle: "Necesidades del día a día", budgetBody: "Supermercado, transporte y gastos diarios", budgetRecorded: "Gasto de ejemplo", budgetLimit: "Límite planificado", debtTitle: "Tarjeta de crédito", debtBody: "Mantén a la vista tu próximo pago", balanceOwed: "Monto registrado por pagar", nextPayment: "Pago planificado",
  goalCaveat: "Una meta es una intención. No reserva dinero ni lo mueve fuera de una cuenta.", budgetCaveat: "Un presupuesto es una vista del gasto. No mueve dinero ni lo resta por segunda vez.",
  planEmpty: "Espacio para tu próximo paso", planEmptyBody: "Reúne una meta, un presupuesto o un pago en el mismo panorama.",
  searchTitle: "Retoma donde lo dejaste", searchPlaceholder: "Busca cuentas, actividad y conversaciones de ejemplo", searchLabel: "Buscar registros de ejemplo", all: "Todo", conversations: "Conversaciones", plans: "Planes", searchCategories: "Categorías de búsqueda", sampleResults: "Resultados de ejemplo locales", noResults: "No hay resultados de ejemplo", noResultsBody: "Prueba otra palabra o borra los filtros.", clearSearch: "Borrar búsqueda", clearFilter: "Quitar filtro de cuenta",
  searchEmpty: "Aquí será más fácil encontrar tus registros", searchEmptyBody: "Las cuentas, movimientos, planes y conversaciones conservarán su contexto original.",
  updateIntro: "Cambios que merecen otra mirada.", updateBalance: "Un saldo necesita revisión", updateBalanceBody: "El saldo observado del ejemplo difiere del registrado. Revisa la base antes de corregirlo.",
  updatePayment: "Se acerca un pago", updatePaymentBody: "El plan de tarjeta de ejemplo tiene un pago el 30 de septiembre. No se ha registrado como pagado.", updateImport: "Un estado de cuenta necesita revisión", updateImportBody: "Una importación de ejemplo contiene un movimiento incierto. Revísalo antes de que forme parte de tu panorama.",
  review: "Revisar", openPlan: "Abrir plan", updatesEmpty: "Estás al día en este ejemplo", updatesEmptyBody: "Los cambios relevantes aparecerían aquí con su fuente y un siguiente paso claro.",
  settingsIntro: "Haz que Argus se sienta tuyo.", personalDetails: "Datos personales", personalDetailsBody: "Nombre, foto e información del perfil", app: "App", account: "Cuenta", support: "Ayuda", preferences: "Preferencias", preferencesBody: "Apariencia e idioma", appearance: "Apariencia", appearanceBody: "Claro, oscuro o del sistema", language: "Idioma", languageBody: "English o Español (Latinoamérica)", browserPreferences: "La apariencia y el idioma usan las preferencias del navegador. No se actualiza ningún perfil de cuenta.",
  personalization: "Personalización", personalizationBody: "Cómo Argus trabaja con tu contexto", security: "Seguridad", securityBody: "Inicio de sesión y protección de la cuenta", dataPrivacy: "Datos y privacidad", usage: "Uso", usageBody: "Tu actividad y límites",
  notifications: "Notificaciones", notificationsBody: "Elige las novedades que recibes", dataControls: "Controles de datos", dataControlsBody: "Tus registros y privacidad", archivedChats: "Conversaciones archivadas", archivedBody: "Vuelve a conversaciones anteriores", help: "Ayuda y comentarios", helpBody: "Encuentra ayuda y comparte tu opinión", about: "Acerca de Argus", aboutBody: "Un panorama más claro de tu dinero", profileSample: "Identidad de ejemplo. Esta página no ha iniciado sesión por ti.",
  recents: "Recientes", newChat: "Nuevo chat", temporary: "Temporal", temporaryTitle: "Vista previa del chat temporal", temporaryBody: "Esto muestra dónde van los controles de chat temporal. No activa un modo de privacidad, cambia la retención ni da acceso al contexto personal.", temporaryContext: "El uso de contexto personal necesita un contrato de permisos separado y verificado.",
  searchRecents: "Buscar conversaciones de ejemplo", recentMoney: "Espacio para un fondo de emergencia", recentMarket: "Entender los ciclos del mercado", recentInvest: "Una idea de inversión mensual", recentSample: "Conversación de ejemplo de solo lectura", recentsEmpty: "Aquí no hay conversaciones de ejemplo", recentsNoResults: "No hay conversaciones de ejemplo que coincidan", searchDraftNote: "Inicia un chat con esta búsqueda como borrador editable, sin enviarlo.", newChatNote: "El diseño de nuevo chat está listo. Tu borrador sigue en el cuadro de mensaje.",
  composerLabel: "Mensaje de vista previa sin enviar", composerPlaceholder: "Pregunta lo que quieras sobre dinero…", composerHint: "Cuadro de mensaje de ejemplo. No se envía nada.", send: "Enviar mensaje de vista previa", sendNotice: "Tu borrador no se ha enviado. Esta vista previa no llama a modelos. Abre el chat actual para preguntar a Argus.", attach: "Agregar archivo", voice: "Entrada de voz", suggestions: "Temas para explorar", chipMoney: "Entender una decisión financiera", chipMarket: "Explorar los mercados", chipAccounts: "Entender mis cuentas", sampleConversationBody: "Este es un ejemplo fijo de diseño. El chat actual de Argus gestiona las conversaciones, cálculos, investigación y pruebas históricas reales.",
  artifactTitle: "Presentación actual de confirmación", artifactNote: "Ejemplo de solo lectura. Esta tarjeta no puede iniciar una prueba.",
  backSettings: "Volver a configuración", backPreferences: "Volver a preferencias", backAccount: "Volver a la cuenta", noSave: "No se guardó nada", stateApplies: "El estado afecta al destino actual; las preferencias siguen disponibles.",
};

export function previewCopy(language: string): PreviewCopy {
  return language.startsWith("es") ? es : en;
}

export const ACCOUNT_TYPES = ["cash", "checking", "savings", "investments", "credit", "debt"] as const;
export type AccountType = (typeof ACCOUNT_TYPES)[number];
export type SampleAccount = {
  readonly id: string; readonly name: CopyKey; readonly type: AccountType;
  readonly currency: "DOP" | "USD"; readonly balance: string | null; readonly isDebt?: boolean;
};

// Authored display fixtures only. No balance, total, difference or forecast is computed.
export const SAMPLE = {
  position: "127,729.25", cashAndBank: "136,229.25", owed: "8,500.00",
  accounts: [
    { id: "everyday", name: "everyday", type: "checking", currency: "DOP", balance: "72,729.25" },
    { id: "pocket", name: "pocket", type: "cash", currency: "DOP", balance: "3,500.00" },
    { id: "safety", name: "safety", type: "savings", currency: "DOP", balance: "60,000.00" },
    { id: "card", name: "card", type: "credit", currency: "DOP", balance: "8,500.00", isDebt: true },
    { id: "dollars", name: "dollars", type: "savings", currency: "USD", balance: "1,250.00" },
    { id: "unknown", name: "unknownAccount", type: "investments", currency: "DOP", balance: null },
  ] as const satisfies readonly SampleAccount[],
  correction: { observed: "72,229.25", difference: "−DOP 500.00" },
  commitments: [
    { id: "payment", title: "creditPayment", date: "sep30", amount: "DOP 2,500.00" },
    { id: "rent", title: "rent", date: "oct01", amount: "DOP 18,000.00" },
    { id: "income", title: "expectedIncome", date: "oct05", amount: "DOP 28,000.00" },
  ] as const,
  activity: [
    { id: "grocery", title: "grocery", account: "everyday", amount: "−DOP 1,850.00" },
    { id: "income", title: "receivedIncome", account: "everyday", amount: "+DOP 12,000.00" },
    { id: "transfer", title: "cashTransfer", account: "pocket", amount: "DOP 1,000.00" },
  ] as const,
  plan: { goalRecorded: "DOP 60,000.00", goalTarget: "DOP 90,000.00", budgetRecorded: "DOP 7,850.00", budgetLimit: "DOP 14,000.00" },
} as const;

export const RECENTS = ["recentMoney", "recentMarket", "recentInvest"] as const satisfies readonly CopyKey[];
export type RecentId = (typeof RECENTS)[number];

// Same typed DCA shape as the existing confirmation tests. No launch callbacks.
export const DCA_CONFIRMATION: StrategyConfirmationPayload = {
  kind: "backtest", title: "AAPL", status: "editing", statusLabel: "Editing",
  strategy_type: "dca_accumulation", asset_class: "equity",
  date_range: { start: "2023-01-03", end: "2025-12-31" },
  rows: [
    { key: "assets", label: "Assets", value: "AAPL" },
    { key: "strategy", label: "Strategy", value: "DCA" },
    { key: "contribution", label: "Contribution", value: "500" },
    { key: "starting_capital", label: "Starting capital", value: "0" },
    { key: "period", label: "Period", value: "2023–2025" },
  ],
  display_facts: { starting_capital: 0, recurring_contribution: 500, contribution_period: "monthly", fees: 0, slippage: 0, benchmark_symbol: "SPY", timeframe: "1D" },
  actions: [],
};
