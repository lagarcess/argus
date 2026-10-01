import SwiftUI
import Charts

struct CuadraoPlanDetail: View {
    let store: CuadraoPlanPreview
    let accounts: CuadraoAccountsPreview
    let planID: UUID
    let spanish: Bool
    var bottomSpace: CGFloat = 90
    @State private var draftAmount: Double?
    @State private var sliderCeiling: Double = 0
    @State private var editing: PlanEditorRoute?
    @State private var exact = false
    @State private var archive = false
    @State private var people = false
    @State private var saved = false
    @Environment(\.dismiss) private var dismiss
    private var plan: CanvasPlan? { store.plan(planID) }
    private func baseline(_ plan: CanvasPlan) -> Double { plan.kind == .budget ? plan.target : plan.monthly }
    private func amount(_ plan: CanvasPlan) -> Double { draftAmount ?? baseline(plan) }
    private func changed(_ plan: CanvasPlan) -> Bool { abs(amount(plan) - baseline(plan)) > 0.01 }

    var body: some View {
        Group {
            if let plan {
                ScrollView {
                    VStack(alignment: .leading, spacing: 28) {
                        heading(plan)
                        if plan.remaining == 0 && plan.kind != .budget {
                            PlanLandscape(look: plan.look).frame(height: 135)
                        } else if plan.kind == .budget && plan.recorded == 0 {
                            VStack(alignment: .leading, spacing: 12) {
                                PlanLandscape(look: plan.look).frame(height: 100)
                                Text(spanish ? "Tu ritmo aparecerá con tus primeros movimientos." : "Your pace will appear with your first transactions.")
                                    .font(.subheadline).foregroundStyle(.secondary)
                            }
                        } else { PlanDetailChart(plan: plan, amount: amount(plan), spanish: spanish, scenarioCeiling: sliderCeiling) }
                        if plan.remaining > 0 || plan.kind == .budget { playground(plan) }
                        facts(plan)
                        if plan.spaceID == "household" { household(plan) }
                        PlanPreviewFootnote(spanish: spanish)
                    }.padding(24).padding(.bottom, bottomSpace)
                }
                .background(WelcomePalette.background).cuadraoSoftScrollEdges()
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Menu {
                            Button { editing = .init(plan: plan) } label: { Label(spanish ? "Editar plan" : "Edit plan", systemImage: "pencil") }
                            Button { archive = true } label: { Label(spanish ? "Archivar" : "Archive", systemImage: "archivebox") }
                        } label: { Image(systemName: "ellipsis").frame(width: 44, height: 44) }
                            .accessibilityLabel(spanish ? "Opciones del plan" : "Plan options").accessibilityIdentifier("plan-detail-options")
                    }
                }
                .sheet(isPresented: $exact) {
                    PlanExactAmount(amount: Binding(get: { amount(plan) }, set: { draftAmount = $0; sliderCeiling = max(sliderCeiling, $0); saved = false }), maximum: 9999999, minimum: 1,
                        title: plan.kind == .budget ? (spanish ? "Mi margen mensual" : "My monthly allowance") : (spanish ? "Cada mes" : "Each month"), currency: plan.currency, spanish: spanish)
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
        .onChange(of: plan) { _, _ in draftAmount = nil; sliderCeiling = 0 }
        .sensoryFeedback(.success, trigger: saved) { _, new in new }
    }

    private func heading(_ plan: CanvasPlan) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text(PlanFormat.space(plan.spaceID, accounts: accounts, spanish: spanish)).font(.subheadline).foregroundStyle(.secondary)
                Spacer()
                Image(systemName: plan.look.symbol).foregroundStyle(plan.look.color).font(.title2)
            }
            Text(plan.name).font(.system(.largeTitle, design: .serif)).fixedSize(horizontal: false, vertical: true)
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(PlanFormat.amount(plan.kind == .debt ? plan.remaining : plan.recorded, currency: plan.currency))
                    .font(.system(size: 34, weight: .regular, design: .rounded)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.6)
                Spacer(minLength: 0)
            }
            Text(plan.kind == .debt ? (spanish ? "por pagar" : "left to pay") : plan.kind.recordedTitle(spanish))
                .font(.subheadline).foregroundStyle(.secondary).padding(.top, -12)
            if plan.remaining == 0 && plan.kind != .budget {
                Label(spanish ? "Lo hiciste. Un plan menos, más posibilidades." : "You did it. One plan down, more possibilities ahead.", systemImage: "checkmark.seal")
                    .font(.subheadline).foregroundStyle(plan.look.color)
            }
        }
    }

    private func playground(_ plan: CanvasPlan) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 8) {
                Text(plan.kind == .budget ? (spanish ? "Dale aire a tu mes." : "Give your month some room.") : (spanish ? "Encuentra tu ritmo." : "Find your rhythm."))
                    .font(.system(.title2, design: .serif))
                if plan.kind == .budget && plan.recorded > 0 {
                    let estimate = plan.projectedValue(at: CanvasForecast.lastDay, monthly: amount(plan))
                    Text(spanish ? "A tu ritmo actual, gastarías \(PlanFormat.amount(estimate, currency: plan.currency)). Cambiar el margen no cambia ese ritmo." : "At your current pace, you'd spend \(PlanFormat.amount(estimate, currency: plan.currency)). Changing the allowance doesn't change that pace.")
                        .font(.subheadline).foregroundStyle(.secondary)
                } else if plan.kind != .budget {
                    Text(plan.months(at: amount(plan)).map { PlanFormat.month(after: $0, spanish: spanish) }
                        ?? (spanish ? "Este aporte no alcanza para llegar." : "This amount won't get you there."))
                        .font(.title3.weight(.medium)).foregroundStyle(plan.look.color).accessibilityIdentifier("plan-estimated-date")
                    if changed(plan), let original = plan.months(at: plan.monthly), let proposed = plan.months(at: amount(plan)), original != proposed {
                        Text(spanish ? "\(abs(original - proposed)) meses \(proposed < original ? "antes" : "después")" : "\(abs(original - proposed)) months \(proposed < original ? "earlier" : "later")")
                            .font(.subheadline.weight(.medium)).foregroundStyle(plan.look.color)
                    }
                    Text(spanish ? "Fecha estimada, manteniendo este aporte." : "Estimated date if you keep this contribution.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            VStack(spacing: 10) {
                HStack {
                    Text(plan.kind == .budget ? (spanish ? "Mi margen" : "My allowance") : (spanish ? "Cada mes" : "Each month")).font(.subheadline)
                    Spacer()
                    Button { exact = true } label: {
                        HStack(spacing: 6) { Text(PlanFormat.amount(amount(plan), currency: plan.currency)).monospacedDigit(); Image(systemName: "pencil").font(.caption) }
                            .font(.subheadline.weight(.medium)).frame(minHeight: 44)
                    }.accessibilityIdentifier("plan-detail-exact")
                }
                Slider(value: Binding(get: { amount(plan) }, set: { draftAmount = $0; saved = false }),
                    in: 1...max(1000, baseline(plan) * 3, sliderCeiling), step: 1)
                    .tint(plan.look.color).accessibilityLabel(spanish ? "Probar otro monto" : "Try another amount")
                    .accessibilityIdentifier("plan-detail-slider")
            }.padding(20).background(plan.look.color.opacity(0.065), in: RoundedRectangle(cornerRadius: 24))
            if plan.kind != .budget {
                ScrollView(.horizontal) {
                    HStack(spacing: 8) {
                        ForEach([3, 6, 12], id: \.self) { months in
                            Button {
                                draftAmount = plan.monthlyAmount(finishingIn: months); sliderCeiling = max(sliderCeiling, draftAmount ?? 0); saved = false
                            } label: {
                                Text(spanish ? "Llegar en \(months) meses" : "Get there in \(months) months")
                                    .font(.caption).padding(.horizontal, 14).frame(minHeight: 44)
                                    .background(WelcomePalette.surface, in: Capsule())
                            }.accessibilityIdentifier("plan-in-\(months)-months")
                        }
                    }
                }.scrollIndicators(.hidden)
            }
            if changed(plan) {
                PlanPrimaryButton(title: spanish ? "Aplicar a mi plan" : "Apply to my plan") {
                    var updated = plan
                    if plan.kind == .budget { updated.target = amount(plan) } else { updated.monthly = amount(plan) }
                    store.save(updated); draftAmount = nil; saved = true
                }.accessibilityIdentifier("plan-detail-apply")
                Button(spanish ? "Deshacer prueba" : "Reset experiment") { draftAmount = nil }
                    .font(.subheadline).frame(maxWidth: .infinity, minHeight: 44).accessibilityIdentifier("plan-detail-reset")
            } else if saved {
                Label(spanish ? "Tu plan, a tu ritmo." : "Your plan, your pace.", systemImage: "checkmark.circle")
                    .font(.subheadline).foregroundStyle(WelcomePalette.pine)
            }
        }
    }

    private func facts(_ plan: CanvasPlan) -> some View {
        DisclosureGroup {
            VStack(alignment: .leading, spacing: 16) {
                LabeledContent(plan.kind.amountTitle(spanish), value: PlanFormat.amount(plan.target, currency: plan.currency))
                LabeledContent(plan.kind.recordedTitle(spanish), value: PlanFormat.amount(plan.recorded, currency: plan.currency))
                if plan.kind == .debt {
                    LabeledContent(spanish ? "Interés anual" : "Annual interest", value: "\(plan.annualRate.formatted())%")
                }
                Text(plan.kind == .budget
                    ? (spanish ? "Proyección simple con 12 días registrados de un mes de 31 días. No es un gasto confirmado." : "Simple projection using 12 recorded days in a 31-day month. This is not confirmed spending.")
                    : (spanish ? "Escenario al 12 de octubre de 2026. Aportes mensuales constantes. Sin rendimientos, compras nuevas ni comisiones. El plan no mueve dinero." : "Scenario as of October 12, 2026. Fixed monthly contributions. No returns, new purchases, or fees. The plan doesn't move money."))
                    .font(.caption).foregroundStyle(.secondary)
            }.font(.subheadline).padding(.top, 16)
        } label: { Text(spanish ? "Los detalles, claros" : "The details, clearly").font(.subheadline.weight(.medium)) }
    }
    private func household(_ plan: CanvasPlan) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(spanish ? "Se hace en equipo." : "Better together.").font(.system(.title2, design: .serif))
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

private struct PlanDetailChart: View {
    let plan: CanvasPlan
    let amount: Double
    let spanish: Bool
    var scenarioCeiling: Double = 0
    private var horizon: Int { plan.kind == .budget ? 31 : min(24, max(6, plan.months(at: plan.monthly) ?? 12)) }
    private func value(_ month: Int, monthly: Double) -> Double {
        plan.projectedValue(at: month, monthly: monthly)
    }
    private var upperBound: Double {
        if plan.kind == .debt { return max(plan.target, plan.remaining * pow(1 + plan.annualRate / 1200, Double(horizon))) * 1.15 }
        if plan.kind == .budget { return max(plan.target * 3, scenarioCeiling, value(horizon, monthly: amount)) * 1.15 }
        return plan.target * 1.15
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Chart {
                RuleMark(y: .value("Target", plan.kind == .budget ? amount : plan.kind == .goal ? plan.target : 0))
                    .foregroundStyle(plan.look.color.opacity(0.3)).lineStyle(StrokeStyle(lineWidth: 1, dash: [2, 4]))
                ForEach(0...horizon, id: \.self) { step in
                    LineMark(x: .value("Month", step), y: .value("Value", value(step, monthly: plan.monthly)), series: .value("Path", "saved"))
                        .foregroundStyle(Color.secondary.opacity(0.3)).lineStyle(StrokeStyle(lineWidth: 2))
                    LineMark(x: .value("Month", step), y: .value("Value", value(step, monthly: amount)), series: .value("Path", "preview"))
                        .foregroundStyle(plan.look.color).lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round, dash: [5, 4]))
                }
            }
            .chartYScale(domain: 0...upperBound)
            .chartYAxis(.hidden).chartXAxis(.hidden).frame(height: 145)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(spanish ? "Proyección ilustrativa del plan. Línea punteada: lo previsto, no progreso registrado." : "Illustrative plan projection. Dashed line: planned, not recorded progress.")
            HStack {
                Text(plan.kind == .budget ? (spanish ? "1 oct." : "Oct 1") : (spanish ? "Hoy" : "Today"))
                Spacer()
                Text(plan.kind == .budget ? (spanish ? "31 oct." : "Oct 31") : (spanish ? "\(horizon) meses" : "\(horizon) months"))
            }.font(.caption2).foregroundStyle(.secondary)
            Text(spanish ? "Línea punteada · proyección" : "Dashed line · projection").font(.caption2).foregroundStyle(.secondary)
        }
    }
}
