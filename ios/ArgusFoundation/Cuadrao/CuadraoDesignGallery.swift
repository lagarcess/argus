import SwiftUI

/// Preview-only reference surface. It uses the components users interact with.
struct CuadraoDesignGallery: View {
    @State private var spanish = !ProcessInfo.processInfo.arguments.contains("--design-english")
    @AppStorage(CuadraoAppearancePicker.storageKey) private var appearance = AppearancePreference.light
    @State private var originalAppearance: AppearancePreference?
    private var dark: Binding<Bool> { Binding(get: { appearance == .dark }, set: { appearance = $0 ? .dark : .light }) }
    @State private var largeText = false
    @State private var raw = ""
    @State private var accountError = ""
    @State private var amount = 0.0
    @State private var planError = ""
    @State private var currency = "DOP"
    @State private var distribution = false
    @State private var period: CanvasHistoryRange = .month
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    controls
                    VStack(alignment: .leading, spacing: 12) {
                        Text(spanish ? "Se siente Cuadrao." : "Feels like Cuadrao.").font(CuadraoTypography.screen)
                        Text(spanish ? "El mismo lenguaje, en cada espacio." : "One language across every space.")
                            .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                    }
                    sample(spanish ? "Tipografía" : "Typography") {
                        Text(spanish ? "Tu panorama." : "Your overview.").font(CuadraoTypography.feature)
                        Text(spanish ? "Tus planes" : "Your plans").font(CuadraoTypography.section)
                        Text(spanish ? "Un lugar para lo que viene." : "A place for what's next.").font(CuadraoTypography.body)
                        Text("DOP 24,580.50").font(CuadraoTypography.amount).foregroundStyle(WelcomePalette.ink)
                            .lineLimit(1).minimumScaleFactor(0.5)
                        Text(spanish ? "Ejemplo · Balance registrado" : "Example · Recorded balance")
                            .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                    }
                    sample(spanish ? "Filas y acciones" : "Rows and actions") {
                        ViewThatFits(in: .horizontal) {
                            HStack { rowLabel; Spacer(); rowAmount }
                            VStack(alignment: .leading, spacing: 8) { rowLabel; rowAmount }
                        }
                        PlanPrimaryButton(title: spanish ? "Continuar" : "Continue") { }
                            .disabled(true).accessibilityIdentifier("gallery-action")
                    }
                    sample(spanish ? "Controles compartidos" : "Shared controls") {
                        HStack {
                            Text(spanish ? "Cuentas" : "Accounts").font(CuadraoTypography.section)
                            Spacer()
                            CuadraoSectionAddButton(title: spanish ? "Añadir cuenta" : "Add account") { }
                        }
                        HStack {
                            CuadraoChoiceMenu(title: spanish ? "Moneda" : "Currency", selection: $currency,
                                values: PlanCurrency.supported, valueTitle: { $0 })
                            Spacer()
                            CuadraoChoiceLabel(title: currency, selectable: false, locked: true)
                        }
                        CuadraoChartViewChoice(distribution: $distribution, spanish: spanish)
                        CuadraoHistoryPeriodChoice(range: $period, spanish: spanish)
                    }
                    sample(spanish ? "Monto en Cuentas" : "Account amount") {
                        CuadraoAmountField(raw: $raw, currency: $currency, error: $accountError, spanish: spanish)
                    }
                    sample(spanish ? "Monto en Plan" : "Plan amount") {
                        PlanAmountInput(value: $amount, currency: $currency, error: $planError,
                                        title: spanish ? "Monto del plan" : "Plan amount", identifier: "gallery-plan-amount", spanish: spanish)
                        Text(spanish ? "Prueba escribir, pegar o borrar. Ambos campos comparten las mismas reglas." : "Try typing, pasting or clearing. Both fields share the same rules.")
                            .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                    }
                }.padding(24)
            }.scrollDismissesKeyboard(.interactively).background(WelcomePalette.background)
                .navigationTitle(spanish ? "Guía visual" : "Visual guide").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(spanish ? "Cerrar" : "Close") { dismiss() } } }
        }.preferredColorScheme(appearance.colorScheme)
            .onAppear { originalAppearance = appearance }
            .onDisappear { if let originalAppearance { appearance = originalAppearance } }
            .environment(\.dynamicTypeSize, largeText ? .accessibility2 : .large)
            .tint(WelcomePalette.pine)
    }
    private var controls: some View {
        VStack(alignment: .leading, spacing: 8) {
            Picker("Language", selection: $spanish) { Text("Español").tag(true); Text("English").tag(false) }
                .pickerStyle(.segmented).accessibilityIdentifier("gallery-language")
            Toggle(spanish ? "Oscuro" : "Dark", isOn: dark).accessibilityIdentifier("gallery-dark")
            Toggle(spanish ? "Texto grande" : "Large text", isOn: $largeText).accessibilityIdentifier("gallery-large-text")
        }.font(CuadraoTypography.supporting)
    }
    private var rowLabel: some View {
        Label(spanish ? "Compra del día" : "Today's purchase", systemImage: "basket")
            .font(CuadraoTypography.body)
    }
    private var rowAmount: some View { Text("DOP 1,250.00").font(CuadraoTypography.rowAmount) }
    private func sample<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(title).font(CuadraoTypography.caption).foregroundStyle(.secondary).accessibilityAddTraits(.isHeader)
            content()
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

#Preview("Cuadrao · Reference gallery") { CuadraoDesignGallery() }
