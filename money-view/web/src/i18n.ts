import { localeSchema, type Locale } from './contracts';
const es = {
  money: 'Tu dinero',
  saved: 'Guardados',
  headline: 'Tu dinero, con más claridad.',
  withClara: 'Con Clara',
  sample: 'Ejemplo ilustrativo',
  syntheticSource: 'Fuente simulada',
  publishedSource: 'Fuente publicada',
  current: 'Tu cuenta actual',
  averageRate: 'tasa promedio pagada',
  currentRate: 'tasa anual declarada',
  illustration: 'Valores ilustrativos',
  comparison: 'Comparación',
  days: 'días',
  finalValue: 'valor al final del plazo',
  realValue: 'poder de compra ilustrativo',
  interest: 'interés calculado',
  inflation: 'Inflación anual ilustrativa',
  effective: 'tasa anual equivalente calculada',
  fees: 'comisiones incluidas',
  rounding:
    'El cálculo usa todos los decimales. Este recibo redondea los valores para mostrarlos, por eso las operaciones numéricas son aproximadas.',
  sourceAndMath: 'Fuentes y cálculo',
  sourceDocument: 'Abrir documento fuente',
  inputs: 'Datos confirmados',
  recorded: 'Registrados el',
  assumption: 'Supuesto confirmado',
  userSource: 'Dato que confirmaste',
  close: 'Cerrar fuentes',
  formula: 'Cómo se calculó',
  amount: 'Monto',
  horizon: 'Plazo en días',
  country: 'País',
  currency: 'Moneda',
  currentInput: 'Tasa anual de tu cuenta (%)',
  baselineHint: 'Si lo dejas vacío, confirmas una base de efectivo sin intereses.',
  confirm: 'Confirmar y calcular',
  confirmTitle: 'Confirma tus datos',
  confirmHelp: 'Puedes ajustar estos datos antes de calcular.',
  expired: 'Esta confirmación venció. Envía otra vez el ejemplo para crear una nueva.',
  send: 'Enviar mensaje',
  placeholder: 'Escribe un mensaje...',
  useExample: 'Usar ejemplo',
  welcome:
    'Compara ahorros y certificados a partir de un monto y un plazo. Primero confirmamos los datos.',
  demoHelp:
    'Prueba un ejemplo preparado. El texto libre necesita un modelo conectado; esta demostración no lo tiene.',
  emptyTitle: 'Un punto de partida para tu dinero.',
  emptyBody:
    'Usa el ejemplo en la conversación y confirma los datos para ver una comparación con sus fuentes.',
  emptyAction: 'Empezar con este ejemplo',
  calculating: 'Calculando con los datos confirmados...',
  resultReady:
    'Listo. Los valores ilustrativos están calculados con los datos que confirmaste. Puedes abrir las fuentes y revisar cada paso.',
  save: 'Guardar comparación',
  savedDone: 'Comparación guardada',
  saveHelp: 'Puedes volver a esta comparación si cambia una fuente.',
  working: 'Un momento...',
  loading: 'Cargando tu vista de dinero...',
  retry: 'Volver a intentar',
  noSaved: 'Todavía no hay comparaciones guardadas.',
  noSavedBody: 'Calcula una comparación y guárdala para revisar qué cambia después.',
  openSaved: 'Abrir comparación',
  original: 'Al guardar',
  latest: 'Última revisión',
  before: 'Antes del cambio',
  after: 'Después del cambio',
  beforeAfter: 'Ver antes y después',
  leaderChanged: 'Cambió el mayor valor calculado',
  inflationChanged: 'La inflación cruzó la tasa de referencia',
  notice: 'Una fuente cambió',
  referenceRate: 'Tasa de referencia',
  savedReference: 'Tasa anual equivalente calculada al guardar',
  latestCheckFailed:
    'La última revisión no se pudo completar. Los últimos valores válidos siguen visibles.',
  checkAttempt: 'Revisión intentada el',
  history: 'Tu comparación guardada',
  savedOn: 'Guardada el',
  back: 'Volver a guardados',
  simulate: 'Simular actualización',
  demoControls: 'Prueba de actualización de datos',
  scenario: 'Escenario',
  same_winner: 'Cambian tasas, mismo resultado principal',
  leader_changed: 'Cambia el mayor valor calculado',
  inflation_crossed: 'La inflación cruza la referencia',
  failure: 'Falla la carga de datos',
  loadingSources: 'Revisando las fuentes y tus comparaciones guardadas...',
  readySources: 'Fuentes listas. Los cambios relevantes aparecen abajo.',
  stale: 'No se pudieron actualizar las fuentes. Se conservan los últimos datos válidos.',
  unavailable: 'No hay una fuente completa disponible para calcular.',
  lastGood: 'Última carga válida',
  networkError:
    'No pudimos conectar con Clara. Comprueba que el servidor local siga abierto e inténtalo de nuevo.',
  genericError: 'No se pudo completar la solicitud. Inténtalo de nuevo.',
  invalidResponse:
    'La respuesta no tiene todos los datos necesarios. No se muestran valores incompletos.',
  noModel:
    'Este texto necesita un modelo conectado. En esta demostración puedes usar uno de los ejemplos preparados sin claves.',
  unsupported:
    'Esta comparación admite cuentas de ahorro y certificados con datos disponibles. Prueba uno de los ejemplos preparados.',
  missing: 'Faltan datos para confirmar el monto y el plazo. Puedes usar un ejemplo preparado.',
  conflict:
    'Esta confirmación ya se usó con otros datos. Envía un nuevo mensaje para cambiar la comparación.',
  inputError:
    'Revisa el monto, el plazo y la tasa. Usa números válidos dentro de los límites indicados.',
  disclosure:
    'Las tasas reales son promedios publicados por el regulador; una sucursal puede cotizar algo diferente. Esta demostración utiliza datos simulados.',
  assumptions: 'Supuestos del cálculo',
  noTaxes: 'No se incluyen impuestos ni comisiones sin verificar.',
  constantInflation:
    'La inflación se mantiene constante solo para ilustrar el poder de compra. No es un pronóstico.',
  simpleRate: 'Interés simple anual, sin reinversión; cada año se divide en 365 días.',
  noFx: 'Se compara en una sola moneda, sin conversión de divisas.',
  sourceLoading: 'Abriendo el documento fuente...',
  sourceError: 'No se pudo abrir el documento fuente.',
  sourceRaw: 'Datos del documento',
  receiptDate: 'Fecha simulada de publicación',
  publishedDate: 'Fecha de publicación',
  principal: 'Monto inicial',
  annualFee: 'Comisión anual verificada',
  periodFee: 'Comisión del plazo',
  annualInflation: 'Inflación anual',
  model: 'Modelo de cálculo',
  nominalFormula: 'Valor final = monto + interés − comisiones',
  interestFormula: 'Interés = monto × tasa anual / 100 × días / 365',
  realFormula: 'Poder de compra = valor final / (1 + inflación / 100) ^ (días / 365)',
  savings: 'Ahorros',
  certificate: 'Certificado',
  baseline: 'Base de comparación',
  receipt: 'Ver recibo',
  sourceContext: 'Fuente de tasas e inflación, datos confirmados y fecha del cálculo',
};
export type Copy = typeof es;
const en: Copy = {
  money: 'Your money',
  saved: 'Saved',
  headline: 'Your money, with more clarity.',
  withClara: 'With Clara',
  sample: 'Illustrative example',
  syntheticSource: 'Simulated source',
  publishedSource: 'Published source',
  current: 'Your current account',
  averageRate: 'average rate paid on balances',
  currentRate: 'stated annual rate',
  illustration: 'Illustrative values',
  comparison: 'Comparison',
  days: 'days',
  finalValue: 'value at the end of the term',
  realValue: 'illustrative purchasing power',
  interest: 'calculated interest',
  inflation: 'Illustrative annual inflation',
  effective: 'calculated annual equivalent rate',
  fees: 'included fees',
  rounding:
    'Calculations use full precision. This receipt rounds values for display, so the numeric equations are approximate.',
  sourceAndMath: 'Sources and calculation',
  sourceDocument: 'Open source document',
  inputs: 'Confirmed inputs',
  recorded: 'Recorded on',
  assumption: 'Confirmed assumption',
  userSource: 'Your confirmed input',
  close: 'Close sources',
  formula: 'How it was calculated',
  amount: 'Amount',
  horizon: 'Term in days',
  country: 'Country',
  currency: 'Currency',
  currentInput: 'Your account annual rate (%)',
  baselineHint: 'Leave blank to confirm a cash baseline without interest.',
  confirm: 'Confirm and calculate',
  confirmTitle: 'Confirm your inputs',
  confirmHelp: 'You can adjust these inputs before calculating.',
  expired: 'This confirmation expired. Send the example again to create a new one.',
  send: 'Send message',
  placeholder: 'Write a message...',
  useExample: 'Use example',
  welcome:
    'Compare savings and certificates using an amount and a term. We confirm the inputs first.',
  demoHelp:
    'Try a prepared example. Free text needs a connected model; this demonstration has none.',
  emptyTitle: 'A starting point for your money.',
  emptyBody:
    'Use the example in the conversation and confirm the inputs to see a comparison with its sources.',
  emptyAction: 'Start with this example',
  calculating: 'Calculating with your confirmed inputs...',
  resultReady:
    'Done. Illustrative values use the inputs you confirmed. Open the sources to review every step.',
  save: 'Save comparison',
  savedDone: 'Comparison saved',
  saveHelp: 'Return to this comparison when a source changes.',
  working: 'One moment...',
  loading: 'Loading your money view...',
  retry: 'Try again',
  noSaved: 'No saved comparisons yet.',
  noSavedBody: 'Calculate a comparison and save it to review what changes later.',
  openSaved: 'Open comparison',
  original: 'When saved',
  latest: 'Latest check',
  before: 'Before the change',
  after: 'After the change',
  beforeAfter: 'See before and after',
  leaderChanged: 'The highest calculated value changed',
  inflationChanged: 'Inflation crossed the reference rate',
  notice: 'A source changed',
  referenceRate: 'Reference rate',
  savedReference: 'Calculated annual equivalent rate when saved',
  latestCheckFailed:
    'The latest check could not be completed. The last valid values remain visible.',
  checkAttempt: 'Check attempted on',
  history: 'Your saved comparison',
  savedOn: 'Saved on',
  back: 'Back to saved',
  simulate: 'Simulate update',
  demoControls: 'Data update demonstration',
  scenario: 'Scenario',
  same_winner: 'Rates change, same leading result',
  leader_changed: 'Highest calculated value changes',
  inflation_crossed: 'Inflation crosses the reference',
  failure: 'Data load fails',
  loadingSources: 'Checking sources and your saved comparisons...',
  readySources: 'Sources are ready. Relevant changes appear below.',
  stale: 'Sources could not be updated. The last valid data is preserved.',
  unavailable: 'No complete source is available to calculate.',
  lastGood: 'Last valid load',
  networkError: 'Could not connect to Clara. Check that the local server is running and try again.',
  genericError: 'The request could not be completed. Try again.',
  invalidResponse: 'The response is missing required data. Incomplete values are not displayed.',
  noModel:
    'This text needs a connected model. Use a prepared example in this demonstration without API keys.',
  unsupported:
    'This comparison supports savings accounts and certificates with available data. Try a prepared example.',
  missing:
    'Some inputs are missing to confirm the amount and term. You can use a prepared example.',
  conflict:
    'This confirmation was already used with different inputs. Send a new message to change the comparison.',
  inputError: 'Check the amount, term and rate. Use valid numbers within the displayed limits.',
  disclosure:
    'Real rates are regulator-published averages; a branch quote may differ. This demonstration uses simulated data.',
  assumptions: 'Calculation assumptions',
  noTaxes: 'Taxes and unverified fees are excluded.',
  constantInflation:
    'Inflation is held constant only to illustrate purchasing power. This is not a forecast.',
  simpleRate: 'Simple annual interest without reinvestment; each year is divided into 365 days.',
  noFx: 'One currency is compared, without foreign exchange conversion.',
  sourceLoading: 'Opening source document...',
  sourceError: 'Could not open the source document.',
  sourceRaw: 'Document data',
  receiptDate: 'Simulated publication date',
  publishedDate: 'Publication date',
  principal: 'Starting amount',
  annualFee: 'Verified annual fee',
  periodFee: 'Fee for the term',
  annualInflation: 'Annual inflation',
  model: 'Calculation model',
  nominalFormula: 'End value = amount + interest − fees',
  interestFormula: 'Interest = amount × annual rate / 100 × days / 365',
  realFormula: 'Purchasing power = end value / (1 + inflation / 100) ^ (days / 365)',
  savings: 'Savings',
  certificate: 'Certificate',
  baseline: 'Comparison baseline',
  receipt: 'View receipt',
  sourceContext: 'Rate and inflation sources, confirmed inputs and calculation date',
};
export const copy = (locale: Locale): Copy => (locale === 'en' ? en : es);
export function initialLocale(): Locale {
  try {
    const parsed = localeSchema.safeParse(localStorage.getItem('clara-locale'));
    return parsed.success ? parsed.data : 'es-419';
  } catch {
    return 'es-419';
  }
}
export const date = (value: string, locale: Locale) =>
  new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).format(
    new Date(value.length === 10 ? `${value}T12:00:00` : value),
  );
export const money = (value: string, currency: string, locale: Locale) =>
  new Intl.NumberFormat(locale, { style: 'currency', currency, currencyDisplay: 'code' }).format(
    Number(value),
  );
export const percent = (value: string, locale: Locale) =>
  `${new Intl.NumberFormat(locale, { maximumFractionDigits: 4 }).format(Number(value))}%`;
export function errorText(code: string, t: Copy): string {
  if (code.includes('expired')) return t.expired;
  if (code.includes('consumed') || code.includes('conflict')) return t.conflict;
  if (code.includes('model') || code.includes('demo_example') || code.includes('interpret'))
    return t.noModel;
  if (code.includes('unsupported') || code.includes('dataset')) return t.unsupported;
  if (code.includes('validation') || code.includes('invalid_input') || code === 'invalid_request')
    return t.inputError;
  if (code === 'network_error') return t.networkError;
  if (code === 'invalid_response') return t.invalidResponse;
  return t.genericError;
}
