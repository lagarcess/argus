import SwiftUI

struct CuadraoPlanDetail: View {
    let store: CuadraoPlanPreview
    let accounts: CuadraoAccountsPreview
    let planID: UUID
    let spanish: Bool
    var bottomSpace: CGFloat = 90
    @State private var chatFocus: CanvasChatFocus?
    @State private var editing: PlanEditorRoute?
    @State private var archive = false
    @State private var people = false
    @State private var progressEntry = false
    @Environment(\.dismiss) private var dismiss
    private var plan: CanvasPlan? { store.plan(planID) }

    var body: some View {
        Group {
            if let plan {
                CuadraoPlanDetailPage(bottomSpace: bottomSpace) {
                    heading(plan)
                    if plan.remaining == 0 && plan.kind != .budget {
                        PlanLandscape(look: plan.look).frame(height: 135)
                    } else if plan.kind == .budget && plan.recorded == 0 {
                        VStack(alignment: .leading, spacing: 12) {
                            PlanLandscape(look: plan.look).frame(height: 100)
                            Text(spanish ? "Tu ritmo aparecerá con tus primeros movimientos." : "Your pace will appear with your first transactions.")
                                .font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                    if plan.remaining > 0 || plan.kind == .budget {
                        CuadraoPlanWhatIf(scenario: plan.scenario, spanish: spanish) { amount in
                            var updated = plan
                            if plan.kind == .budget { updated.target = amount } else { updated.monthly = amount }
                            store.save(updated)
                        }
                    }
                    Button { progressEntry = true } label: {
                        Label(spanish ? "Actualizar progreso" : "Update progress", systemImage: "plus.circle").frame(minHeight: 44)
                    }.accessibilityIdentifier("plan-record-progress")
                    facts(plan)
                    if plan.spaceID == "household" { household(plan) }
                    PlanPreviewFootnote(spanish: spanish)
                }
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        CuadraoPlanDetailOptions(spanish: spanish) {
                            Button(spanish ? "Preguntar a Cuadrao" : "Ask Cuadrao", systemImage: "bubble") { chatFocus = .plan(id: plan.id, title: plan.name) }
                                .accessibilityIdentifier("plan-open-chat")
                            Button { editing = .init(plan: plan) } label: { Label(spanish ? "Editar plan" : "Edit plan", systemImage: "pencil") }
                            Button { archive = true } label: { Label(spanish ? "Archivar" : "Archive", systemImage: "archivebox") }
                        }
                    }
                }
                .sheet(isPresented: $progressEntry) {
                    PlanExactAmount(amount: Binding(get: { plan.recorded }, set: { value in
                        var updated = plan; updated.recorded = value; store.save(updated)
                    }), maximum: plan.kind == .debt ? plan.target : CanvasMoney.maximumValue, title: plan.kind.recordedTitle(spanish), currency: plan.currency, spanish: spanish)
                }
                .confirmationDialog(spanish ? "¿Dejamos este plan en pausa?" : "Put this plan aside?", isPresented: $archive, titleVisibility: .visible) {
                    Button(spanish ? "Archivar plan" : "Archive plan") { store.archive(plan.id, true); dismiss() }
                } message: { Text(spanish ? "Podrás retomarlo desde Archivados. Su progreso se conserva." : "You can restore it from Archived. Its progress stays with it.") }
            } else {
                ContentUnavailableView(spanish ? "Este plan ya no está aquí" : "This plan is no longer here", systemImage: "square.stack")
            }
        }
        .navigationTitle("").navigationBarTitleDisplayMode(.inline).toolbar(.visible, for: .navigationBar)
        .sheet(item: $editing) { route in
            CuadraoPlanEditor(store: store, accounts: accounts, initial: route.plan, spanish: spanish)
        }
        .sheet(isPresented: $people) { CuadraoHouseholdSheet(data: accounts, spanish: spanish) }
        .contextualCuadrao(focus: $chatFocus, spanish: spanish)
    }

    private func heading(_ plan: CanvasPlan) -> some View {
        CuadraoPlanDetailHeading(display: .init(
            name: plan.name, space: PlanFormat.space(plan.spaceID, accounts: accounts, spanish: spanish), look: plan.look,
            amount: PlanFormat.amount(plan.kind == .debt ? plan.remaining : plan.recorded, currency: plan.currency),
            annotation: plan.kind == .debt ? (spanish ? "por pagar" : "left to pay") : plan.kind.recordedTitle(spanish))) {
            if plan.remaining == 0 && plan.kind != .budget {
                Label(spanish ? "Lo hiciste. Un plan menos, más posibilidades." : "You did it. One plan down, more possibilities ahead.", systemImage: "checkmark.seal").font(.subheadline).foregroundStyle(plan.look.color)
            }
        }
    }

    private func facts(_ plan: CanvasPlan) -> some View {
        CuadraoPlanDetailFacts(spanish: spanish) {
            LabeledContent(plan.kind.amountTitle(spanish), value: PlanFormat.amount(plan.target, currency: plan.currency))
            LabeledContent(plan.kind.recordedTitle(spanish), value: PlanFormat.amount(plan.recorded, currency: plan.currency))
            if plan.kind == .debt {
                LabeledContent(spanish ? "Interés anual" : "Annual interest", value: "\(plan.annualRate.formatted())%")
            }
            Text(plan.scenario.disclosure(spanish: spanish))
                .font(.caption).foregroundStyle(.secondary)
        }
    }
    private func household(_ plan: CanvasPlan) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(spanish ? "Se hace en equipo." : "Better together.").font(CuadraoTypography.section)
                Spacer()
                Button { people = true } label: { Image(systemName: "person.2").frame(width: 44, height: 44) }
                    .accessibilityLabel(spanish ? "Personas del hogar" : "Household members")
            }
            Text(plan.kind == .budget ? (spanish ? "Un margen de \(PlanFormat.amount(plan.target, currency: plan.currency)) para lo de ustedes." : "An allowance of \(PlanFormat.amount(plan.target, currency: plan.currency)) for what you share.") : (spanish ? "\(PlanFormat.amount(plan.monthly, currency: plan.currency)) al mes entre ustedes." : "\(PlanFormat.amount(plan.monthly, currency: plan.currency)) a month between you."))
                .font(.subheadline)
            Text(plan.kind == .budget ? (spanish ? "El margen es compartido. Las cuentas personales de cada quien siguen siendo privadas." : "The allowance is shared. Each person's personal accounts stay private.") : (spanish ? "Es el aporte previsto del hogar, no dinero recibido. El progreso registrado se muestra arriba." : "This is the household's planned contribution, not money received. Recorded progress is shown above."))
                .font(.caption).foregroundStyle(.secondary)
        }.padding(22).background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 24))
    }
}
