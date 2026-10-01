import SwiftUI

struct CuadraoPlanEditor: View {
    let store: CuadraoPlanPreview
    let accounts: CuadraoAccountsPreview
    let initial: CanvasPlan
    let spanish: Bool
    var onSave: ((UUID) -> Void)?
    @State private var draft: CanvasPlan
    @State private var amountErrors: [String: String] = [:]
    @State private var showDetails = false
    @State private var discard = false
    @FocusState private var nameFocused: Bool
    @Environment(\.dismiss) private var dismiss
    private var editing: Bool { store.plan(initial.id) != nil }
    private var valid: Bool {
        amountErrors.allSatisfy { id, error in error.isEmpty || (draft.kind == .budget && id == "plan-monthly") } && !draft.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && draft.target.isFinite && (0.01...CanvasMoney.maximumValue).contains(draft.target)
        && draft.recorded.isFinite && (0...CanvasMoney.maximumValue).contains(draft.recorded)
        && (draft.kind == .budget || (draft.monthly.isFinite && (0.01...CanvasMoney.maximumValue).contains(draft.monthly)))
        && draft.annualRate.isFinite && (0...100).contains(draft.annualRate)
        && (draft.kind != .debt || draft.recorded <= draft.target)
        && accounts.visibleSpaces.contains { $0.id == draft.spaceID }
    }
    init(store: CuadraoPlanPreview, accounts: CuadraoAccountsPreview, initial: CanvasPlan, spanish: Bool, onSave: ((UUID) -> Void)? = nil) {
        self.store = store; self.accounts = accounts; self.initial = initial; self.spanish = spanish; self.onSave = onSave
        _draft = State(initialValue: initial)
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if !editing { kindPicker }
                    HStack(spacing: 18) {
                        PlanLandscape(look: draft.look).frame(width: 64, height: 70)
                        VStack(alignment: .leading, spacing: 8) {
                            Text(spanish ? "Dale un nombre." : "Make it yours.").font(CuadraoTypography.section)
                            TextField(spanish ? "Por ejemplo, mi próximo viaje" : "For example, my next trip", text: $draft.name)
                                .font(.body).focused($nameFocused).submitLabel(.done).onSubmit { nameFocused = false }
                                .accessibilityIdentifier("plan-name")
                        }
                    }
                    VStack(spacing: 0) {
                        amountRow(draft.kind.amountTitle(spanish), value: $draft.target, id: "plan-target", primary: true)
                        if draft.kind != .budget {
                            Divider().padding(.horizontal, 18)
                            amountRow(spanish ? "Cada mes" : "Each month", value: $draft.monthly, id: "plan-monthly")
                        }
                    }.background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 20))
                    HStack {
                        Menu {
                            ForEach(accounts.visibleSpaces) { space in Button(space.title(spanish)) { draft.spaceID = space.id } }
                        } label: {
                            Label(PlanFormat.space(draft.spaceID, accounts: accounts, spanish: spanish), systemImage: draft.spaceID == "household" ? "person.2" : "person")
                                .font(.subheadline).frame(minHeight: 44)
                        }.accessibilityIdentifier("plan-edit-space")
                        Spacer()
                    }
                    if !editing {
                        Text(spanish ? "La moneda queda fija al crear el plan." : "Currency is fixed once you create the plan.").font(.caption).foregroundStyle(.secondary)
                    }
                    if draft.spaceID == "household" {
                        Text(spanish ? "Este plan pertenece a Hogar. Sus miembros podrán verlo; tus cuentas personales siguen siendo privadas." : "This plan belongs to Household. Its members will see it; your personal accounts stay private.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    DisclosureGroup(spanish ? "Darle mi estilo" : "Make it mine") {
                        PlanLookPicker(look: $draft.look, spanish: spanish).padding(.top, 12)
                    }.font(.subheadline)
                    DisclosureGroup(isExpanded: $showDetails) {
                        VStack(spacing: 12) {
                            amountRow(draft.kind.recordedTitle(spanish), value: $draft.recorded, id: "plan-recorded")
                            if draft.kind == .debt {
                                HStack {
                                    Text(spanish ? "Interés anual (%)" : "Annual interest (%)")
                                    TextField("0", value: $draft.annualRate, format: .number).keyboardType(.decimalPad).multilineTextAlignment(.trailing)
                                        .accessibilityIdentifier("plan-rate")
                                }.padding(18)
                                Text(spanish ? "La estimación supone una tasa fija, pagos mensuales, sin compras nuevas ni comisiones." : "The estimate assumes a fixed rate, monthly payments, no new purchases or fees.")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }.padding(.top, 12)
                    } label: { Text(spanish ? "Punto de partida" : "Starting point").font(.subheadline.weight(.medium)) }
                    if draft.kind == .debt && !showDetails {
                        Text(spanish ? "Supuesto: interés anual de \(draft.annualRate.formatted())%. Puedes cambiarlo en Punto de partida." : "Assumption: \(draft.annualRate.formatted())% annual interest. Change it in Starting point.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    if draft.kind != .budget {
                        let months = draft.months(at: draft.monthly)
                        VStack(alignment: .leading, spacing: 5) {
                            Text(months.map { $0 == 0 ? (spanish ? "Ya llegaste." : "You're there.") : PlanFormat.month(after: $0, spanish: spanish) }
                                 ?? (spanish ? "Prueba un aporte mayor" : "Try a higher amount"))
                                .font(CuadraoTypography.section).foregroundStyle(WelcomePalette.pine)
                            Text(spanish ? "Fecha estimada con este ritmo. Puedes ajustarlo después." : "Estimated date at this pace. You can adjust it later.")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    if !valid {
                        Text(spanish ? "Añade un nombre y revisa los montos." : "Add a name and check the amounts.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    PlanPreviewFootnote(spanish: spanish)
                }.padding(24)
            }.safeAreaInset(edge: .bottom) {
                PlanPrimaryButton(title: editing ? (spanish ? "Guardar cambios" : "Save changes") : (spanish ? "Crear plan" : "Create plan")) {
                        draft.name = draft.name.trimmingCharacters(in: .whitespacesAndNewlines)
                        if draft.kind == .budget { draft.monthly = draft.target }
                        store.save(draft); dismiss(); onSave?(draft.id)
                    }.disabled(!valid).opacity(valid ? 1 : 0.45).accessibilityIdentifier("plan-save")
                    .padding(.horizontal, 24).padding(.vertical, 12).background(.regularMaterial)
            }.scrollDismissesKeyboard(.interactively).background(WelcomePalette.background)
                .navigationTitle(editing ? (spanish ? "Editar plan" : "Edit plan") : (spanish ? "Un nuevo plan" : "A new plan"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button(spanish ? "Cancelar" : "Cancel") { if draft != initial { discard = true } else { dismiss() } }
                    }
                    ToolbarItemGroup(placement: .keyboard) {
                        Spacer(); Button(spanish ? "Listo" : "Done") { UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil) }
                    }
                }
                .confirmationDialog(spanish ? "¿Descartar cambios?" : "Discard changes?", isPresented: $discard, titleVisibility: .visible) {
                    Button(spanish ? "Descartar" : "Discard", role: .destructive) { dismiss() }
                }
        }.sensoryFeedback(.selection, trigger: draft.look)
            .presentationDragIndicator(.visible).interactiveDismissDisabled(draft != initial)
    }
    private var kindPicker: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(spanish ? "¿Qué tienes en mente?" : "What do you have in mind?").font(CuadraoTypography.section)
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 8) { kindButtons }
                VStack(alignment: .leading, spacing: 8) { kindButtons }
            }
        }
    }
    private var kindButtons: some View {
        ForEach(CanvasPlanKind.allCases) { kind in
            Button { draft.kind = kind } label: {
                Text(kind == .goal ? (spanish ? "Meta" : "Goal") : kind == .budget ? (spanish ? "Mi mes" : "My month") : (spanish ? "Deuda" : "Debt")).font(.subheadline)
                    .padding(.horizontal, 14).frame(minHeight: 44)
                    .foregroundStyle(draft.kind == kind ? WelcomePalette.onAccent : WelcomePalette.ink)
                    .background(draft.kind == kind ? WelcomePalette.pine : WelcomePalette.surface, in: Capsule())
            }.accessibilityIdentifier("plan-kind-\(kind.rawValue)").accessibilityAddTraits(draft.kind == kind ? .isSelected : [])
        }
    }
    private func amountRow(_ title: String, value: Binding<Double>, id: String, primary: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            PlanAmountInput(value: value, currency: $draft.currency, error: $amountErrors.message(for: id), title: title,
                            identifier: id, spanish: spanish, currencySelectable: primary && !editing,
                            showCurrencyLock: primary && editing, prominent: primary)
        }.padding(18)
    }
}
