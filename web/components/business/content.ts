export type { BusinessLocale } from "@/lib/business-site";

const es = {
  navigation: {
    business: "Business",
    personal: "Personal",
    approach: "Cómo funciona",
    about: "Nosotros",
    demo: "Agenda una demo",
    menu: "Abrir menú",
    close: "Cerrar menú",
    label: "Navegación principal",
    language: "Idioma",
    back: "Volver a Business",
    skip: "Ir al contenido",
  },
  hero: {
    first: "Tu negocio,",
    second: "claro y cuadrao.",
    description:
      "Menos papeles sueltos. Más claridad sobre lo que entra, lo que sale y lo que falta por cobrar.",
    explore: "Explora la idea",
    stage: "En desarrollo, contigo desde el principio.",
  },
  preview: {
    title: "Tu negocio, en perspectiva.",
    note: "Vista ilustrativa · datos de ejemplo",
    tabs: ["Resumen", "Por cobrar", "Gastos"],
    income: "Entradas",
    expenses: "Salidas",
    difference: "Diferencia del mes",
    cash: "Movimientos de caja",
    pending: "Por cobrar",
    invoice: "Factura de ejemplo",
    due: "Vence",
    client: "Cliente de ejemplo",
    total: "Total por cobrar",
    category: "Concepto",
    expenseTitle: "Cada salida, en contexto.",
    expenseNote: "Un ejemplo de cómo podrías ver los gastos de tu negocio.",
    pendingNote: "Una vista de ejemplo para tener lo pendiente a mano.",
    expenseTotal: "Total de salidas",
    month: "Mes",
    monthLabel: "Mayo · ejemplo",
    chartLabel:
      "Entradas y salidas de enero a junio, en pesos dominicanos. Datos de ejemplo.",
    months: ["Ene", "Feb", "Mar", "Abr", "May", "Jun"],
    expenseLabels: ["Materiales", "Alquiler", "Servicios", "Transporte"],
    tableAmount: "Monto",
    pendingStatus: "Pendiente",
    tablist: "Vistas del producto ilustrativo",
  },
  benefits: [
    {
      label: "01 / ORGANIZA",
      title: "Cada papel, en su sitio.",
      body: "Estamos creando un lugar para reunir facturas, comprobantes y documentos del negocio. Ordenados y fáciles de encontrar.",
    },
    {
      label: "02 / ENTIENDE",
      title: "Lo pendiente, a la vista.",
      body: "Nuestra propuesta: ver lo que tienes por cobrar y por pagar, sin perderte entre hojas sueltas o conversaciones.",
    },
    {
      label: "03 / DECIDE",
      title: "Tus números, con contexto.",
      body: "Queremos ayudarte a entender cómo va tu negocio, con información clara para decidir con más contexto.",
    },
  ],
  approach: {
    title: "Empezamos por entender tu negocio.",
    body: "Estamos construyendo Cuadrao para quienes llevan el negocio todos los días. La primera conversación empieza por tu forma de trabajar.",
    steps: [
      {
        title: "Nos cuentas cómo trabajas",
        body: "Qué llevas hoy, dónde lo anotas y qué te cuesta mantener al día.",
      },
      {
        title: "Vemos juntos la propuesta",
        body: "Una mirada a lo que estamos preparando y una conversación sobre lo que necesitas.",
      },
      {
        title: "Definimos el próximo paso",
        body: "Si hay un buen encaje, acordamos contigo cómo empezar.",
      },
    ],
  },
  founder: {
    label: "DETRÁS DE CUADRAO",
    title: "Tecnología con alguien del otro lado.",
    body: "Soy Lucas, fundador de Cuadrao. Mi experiencia está en tecnología, aprendizaje automático y ciencia de datos. Ahora estoy construyendo Cuadrao y hablando directamente con dueños de negocios para entender lo que necesitan.",
    role: "Fundador de Cuadrao",
  },
  faqLabel: "Preguntas frecuentes",
  faqs: [
    {
      question: "¿Ya puedo usar Cuadrao?",
      answer:
        "Cuadrao para negocios está en desarrollo. Estamos conversando con dueños de negocios para entender sus necesidades y dar forma a la propuesta. Esta página muestra una vista ilustrativa, no una aplicación disponible.",
    },
    {
      question: "¿Cuánto cuesta?",
      answer:
        "Todavía estamos definiendo la propuesta y los precios. La primera conversación nos ayuda a entender tu negocio y ver si hay un buen encaje.",
    },
  ],
  closing: {
    first: "Vamos a poner tu",
    second: "negocio en claro.",
    body: "Cuéntanos cómo trabajas. Veamos si Cuadrao encaja contigo.",
    local: "Hecho pensando en los negocios de aquí.",
    footerLabel: "Navegación al pie",
  },
  demo: {
    first: "Hablemos de",
    second: "tu negocio.",
    body: "Queremos entender cómo trabajas y mostrarte lo que estamos construyendo.",
    steps: [
      "Tu forma de trabajar",
      "Una mirada a Cuadrao",
      "Un próximo paso, juntos",
    ],
    noScript:
      "Activa JavaScript para probar este formulario local. No se enviará ningún dato.",
    notice:
      "Prototipo local. Este formulario no envía datos ni agenda una reunión.",
    name: "Tu nombre",
    business: "Nombre del negocio",
    email: "Correo electrónico",
    description: "¿Qué te gustaría tener más claro?",
    optional: "(opcional)",
    namePlaceholder: "Ej. Ana Pérez",
    businessPlaceholder: "Ej. Café del Parque",
    emailPlaceholder: "Ej. tu@negocio.com",
    descriptionPlaceholder: "Cuéntanos en pocas palabras…",
    submit: "Vista previa de la solicitud",
    required: "Completa este campo.",
    invalidEmail: "Escribe un correo válido, como tu@negocio.com.",
    reviewTitle: "Así se vería tu solicitud.",
    reviewBody:
      "No se ha enviado nada ni se ha reservado una reunión. Esta vista te permite revisar el formulario localmente.",
    edit: "Editar datos",
    empty: "Sin comentario",
    privacy:
      "No se envía ni se guarda nada en un servidor. Los datos solo se usan en esta vista previa.",
    errors: "Revisa los campos marcados.",
  },
  personal: {
    eyebrow: "CUADRAO PERSONAL",
    title: "Tu dinero también merece estar cuadrao.",
    body: "Estamos preparando Cuadrao para tus finanzas personales. Pronto compartiremos más.",
    status: "En preparación",
    return: "Conoce Cuadrao para negocios",
  },
};

const en: typeof es = {
  navigation: {
    business: "Business",
    personal: "Personal",
    approach: "How it works",
    about: "About us",
    demo: "Book a demo",
    menu: "Open menu",
    close: "Close menu",
    label: "Main navigation",
    language: "Language",
    back: "Back to Business",
    skip: "Skip to content",
  },
  hero: {
    first: "Your business,",
    second: "clear and cuadrao.",
    description:
      "Less scattered paperwork. More clarity on what comes in, what goes out, and what you are still owed.",
    explore: "Explore the idea",
    stage: "In development, with you from the start.",
  },
  preview: {
    title: "Your business, in perspective.",
    note: "Illustrative view · sample data",
    tabs: ["Overview", "Receivables", "Expenses"],
    income: "Money in",
    expenses: "Money out",
    difference: "Monthly difference",
    cash: "Cash movements",
    pending: "Receivables",
    invoice: "Sample invoice",
    due: "Due",
    client: "Sample customer",
    total: "Total receivables",
    category: "Category",
    expenseTitle: "Every expense, in context.",
    expenseNote: "An example of how you could see your business expenses.",
    pendingNote: "A sample view to keep what is outstanding close at hand.",
    expenseTotal: "Total money out",
    month: "Month",
    monthLabel: "May · sample",
    chartLabel:
      "Sample money in and out from January to June, in Dominican pesos",
    months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
    expenseLabels: ["Materials", "Rent", "Utilities", "Transport"],
    tableAmount: "Amount",
    pendingStatus: "Outstanding",
    tablist: "Illustrative product views",
  },
  benefits: [
    {
      label: "01 / ORGANIZE",
      title: "Every paper, in its place.",
      body: "We are creating one place for your business invoices, receipts, and documents. Organized and easy to find.",
    },
    {
      label: "02 / UNDERSTAND",
      title: "Keep the pending in view.",
      body: "Our idea: see what you owe and what you are owed, without getting lost in loose papers or conversations.",
    },
    {
      label: "03 / DECIDE",
      title: "Your numbers, with context.",
      body: "We want to help you understand how your business is doing, with clear information to inform your decisions.",
    },
  ],
  approach: {
    title: "We start by understanding your business.",
    body: "We are building Cuadrao for the people who run their business every day. The first conversation starts with how you work.",
    steps: [
      {
        title: "Tell us how you work",
        body: "What you track today, where you write it down, and what is hard to keep up to date.",
      },
      {
        title: "Explore the idea together",
        body: "A look at what we are preparing and a conversation about what you need.",
      },
      {
        title: "Define the next step",
        body: "If there is a good fit, we agree together on how to begin.",
      },
    ],
  },
  founder: {
    label: "BEHIND CUADRAO",
    title: "Technology with a person on the other side.",
    body: "I am Lucas, the founder of Cuadrao. My background is in technology, machine learning, and data science. I am now building Cuadrao and talking directly with business owners to understand what they need.",
    role: "Founder of Cuadrao",
  },
  faqLabel: "Frequently asked questions",
  faqs: [
    {
      question: "Can I use Cuadrao now?",
      answer:
        "Cuadrao for business is in development. We are talking with business owners to understand their needs and shape the product. This page shows an illustrative preview, not an available application.",
    },
    {
      question: "How much does it cost?",
      answer:
        "We are still defining the product and pricing. The first conversation helps us understand your business and see whether there is a good fit.",
    },
  ],
  closing: {
    first: "Let’s bring clarity",
    second: "to your business.",
    body: "Tell us how you work. Let’s see if Cuadrao fits.",
    local: "Made with local businesses in mind.",
    footerLabel: "Footer navigation",
  },
  demo: {
    first: "Let’s talk about",
    second: "your business.",
    body: "We want to understand how you work and show you what we are building.",
    steps: ["How you work", "A look at Cuadrao", "A next step, together"],
    noScript: "Enable JavaScript to try this local form. No data will be sent.",
    notice: "Local prototype. This form does not send data or book a meeting.",
    name: "Your name",
    business: "Business name",
    email: "Email address",
    description: "What would you like more clarity on?",
    optional: "(optional)",
    namePlaceholder: "E.g. Ana Pérez",
    businessPlaceholder: "E.g. Café del Parque",
    emailPlaceholder: "E.g. you@business.com",
    descriptionPlaceholder: "Tell us in a few words…",
    submit: "Preview your request",
    required: "Complete this field.",
    invalidEmail: "Enter a valid email, such as you@business.com.",
    reviewTitle: "Here is your request preview.",
    reviewBody:
      "Nothing has been sent and no meeting has been booked. This view lets you review the form locally.",
    edit: "Edit details",
    empty: "No comment",
    privacy:
      "Nothing is sent or saved to a server. These details are only used in this preview.",
    errors: "Check the highlighted fields.",
  },
  personal: {
    eyebrow: "CUADRAO PERSONAL",
    title: "Your money deserves to be cuadrao, too.",
    body: "We are preparing Cuadrao for your personal finances. More to come soon.",
    status: "In development",
    return: "Explore Cuadrao for business",
  },
};

export const businessContent = { es, en };
