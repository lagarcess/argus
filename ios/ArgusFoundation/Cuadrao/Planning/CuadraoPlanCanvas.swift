import SwiftUI

struct CuadraoPlanCanvas: View {
    let store: CuadraoPlanPreview
    let accounts: CuadraoAccountsPreview
    let spanish: Bool
    var bottomSpace: CGFloat = 90
    @State private var path: [UUID] = []
    @State private var together = false
    let groups: CuadraoGroupPreview
    @State private var newGroup = false
    @State private var scope = "personal"
    @State private var selectedDay: Int?
    @State private var creation: PlanEditorRoute?
    @State private var resetConfirmation = false
    @State private var showEmpty = false

    private var forecast: CanvasForecast { CanvasForecast(household: scope == "household") }
    private var active: [CanvasPlan] { store.plans.filter { !$0.archived } }
    private var selectedPoint: CanvasForecastPoint? {
        guard let selectedDay else { return nil }
        return (forecast.actual + forecast.projection(daily: store.daily(for: scope)).dropFirst()).first { $0.day == selectedDay }
    }
    private var scopeName: String { PlanFormat.space(scope, accounts: accounts, spanish: spanish) }

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    header
                    Picker(spanish ? "Tus planes" : "Your plans", selection: $together) {
                        Text(spanish ? "Para ti" : "For you").tag(false)
                        Text(spanish ? "En grupo" : "Together").tag(true)
                    }.pickerStyle(.segmented).accessibilityIdentifier("plan-audience")
                    if together {
                        CuadraoGroupCollection(store: groups, spanish: spanish, bottomSpace: bottomSpace, create: { newGroup = true }, open: { path.append($0) })
                    } else {
                        if store.hasForecast { forecastOverview } else { forecastColdStart }
                        plans
                    }
                    PlanPreviewFootnote(spanish: spanish)
                }.padding(.horizontal, 24).padding(.top, 20).padding(.bottom, bottomSpace)
            }
            .scrollIndicators(.hidden)
            .background(WelcomePalette.background)
            .toolbar(.hidden, for: .navigationBar).toolbar(.hidden, for: .tabBar)
            .cuadraoSoftScrollEdges()
            .navigationDestination(for: UUID.self) { id in
                if store.plan(id) != nil {
                    CuadraoPlanDetail(store: store, accounts: accounts, planID: id, spanish: spanish, bottomSpace: bottomSpace)
                } else {
                    CuadraoGroupDetail(store: groups, groupID: id, spanish: spanish, bottomSpace: bottomSpace)
                }
            }
            .sheet(item: $creation) { route in
                CuadraoPlanEditor(store: store, accounts: accounts, initial: route.plan, spanish: spanish) { id in
                    if store.plan(route.plan.id) != nil { path.append(id) }
                }
            }
            .sheet(isPresented: $newGroup) {
                CuadraoGroupEditor(store: groups, spanish: spanish, onSave: { path.append($0) })
            }
            .confirmationDialog(spanish ? "¿Cambiar el escenario de vista previa?" : "Change preview scenario?", isPresented: $resetConfirmation, titleVisibility: .visible) {
                Button(spanish ? "Cambiar escenario" : "Change scenario", role: .destructive) {
                    store.resetExamples(spanish: spanish, empty: showEmpty); groups.resetExamples(spanish: spanish, empty: showEmpty)
                }
            } message: {
                Text(spanish ? "Se reemplazarán solo los planes de esta vista previa." : "Only this preview's plans will be replaced.")
            }
        }.tint(WelcomePalette.pine)
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 6) {
                Text(spanish ? "Lo que viene" : "What’s ahead").font(CuadraoTypography.screen)
                    .accessibilityIdentifier("plan-heading")
                    .contextMenu {
                        Button(spanish ? "Ver primer uso" : "See first use") { showEmpty = true; resetConfirmation = true }
                        Button(spanish ? "Restablecer ejemplos" : "Reset examples") { showEmpty = false; resetConfirmation = true }
                    }
            }
            Spacer()
            Button { if together { newGroup = true } else { creation = PlanEditorRoute(plan: newPlan) } } label: {
                Image(systemName: "plus").font(.system(size: 20, weight: .medium))
                    .frame(width: 44, height: 44).background(WelcomePalette.sage, in: Circle())
            }.accessibilityLabel(together ? (spanish ? "Crear grupo" : "Create group") : (spanish ? "Crear plan" : "Create plan")).accessibilityIdentifier("plan-create")
        }
    }

    private var forecastSpaces: [CanvasSpace] { accounts.visibleSpaces.filter { $0.kind == .personal || $0.kind == .household } }

    private var newPlan: CanvasPlan {
        CanvasPlan(name: "", spaceID: CanvasSpace.personalID)
    }

    private var forecastOverview: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(spanish ? "Tu mes" : "Your month")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                Spacer()
                if forecastSpaces.count > 1 {
                    CuadraoChoiceMenu(title: spanish ? "Espacio del pronóstico" : "Forecast space",
                        selection: Binding(get: { scope }, set: { scope = $0; selectedDay = nil }),
                        values: forecastSpaces.map(\.id),
                        valueTitle: { PlanFormat.space($0, accounts: accounts, spanish: spanish) })
                        .accessibilityLabel(spanish ? "Espacio del pronóstico, \(scopeName)" : "Forecast space, \(scopeName)")
                        .accessibilityIdentifier("plan-forecast-scope")
                } else { CuadraoChoiceLabel(title: scopeName, selectable: false) }
            }

            VStack(alignment: .leading, spacing: 5) {
                Text(selectedPoint.map { "\($0.day) oct. · \($0.day > CanvasForecast.today ? (spanish ? "estimado" : "estimated") : (spanish ? "registrado" : "recorded"))" } ?? (store.dailyAssumptions[scope] == nil ? (spanish ? "Balance estimado al cierre" : "Estimated closing balance") : (spanish ? "Con tu plan, cerrarías con" : "With your plan, you'd end with")))
                    .font(.subheadline).foregroundStyle(.secondary)
                Text(PlanFormat.amount(selectedPoint?.balance ?? forecast.ending(daily: store.daily(for: scope))))
                    .font(CuadraoTypography.amount).monospacedDigit()
                    .contentTransition(.numericText()).minimumScaleFactor(0.65).lineLimit(1)
                    .accessibilityIdentifier("plan-month-ending")
            }
            PlanForecastChart(forecast: forecast, daily: store.daily(for: scope), spanish: spanish, selectedDay: $selectedDay, compact: true)
            NavigationLink {
                CuadraoForecastPlayground(store: store, scope: scope, scopeName: scopeName, spanish: spanish, bottomSpace: bottomSpace)
            } label: {
                HStack {
                    Text(spanish ? "Explorar escenarios" : "Explore scenarios")
                    Image(systemName: "chevron.right").font(.caption2).accessibilityHidden(true)
                }.font(CuadraoTypography.supporting).foregroundStyle(.secondary).frame(minHeight: 44)
            }.buttonStyle(.plain).accessibilityIdentifier("plan-explore")
        }
    }

    private var forecastColdStart: some View {
        VStack(alignment: .leading, spacing: 18) {
            PlanLandscape(look: .sunshine).frame(height: 135)
            Text(spanish ? "Lo que viene empieza aquí." : "What's next starts here.")
                .font(CuadraoTypography.feature)
            Text(spanish ? "Puedes hacer tu primer plan hoy. La proyección llegará cuando tengas movimientos e ingresos previstos." : "Make your first plan today. Your forecast will take shape with transactions and expected income.")
                .font(.subheadline).foregroundStyle(.secondary)
            Button(spanish ? "Explorar un mes de ejemplo" : "Explore an example month") {
                store.enableForecastExample()
            }.font(.subheadline.weight(.medium)).frame(minHeight: 44)
        }
    }

    private var plans: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(spanish ? "Tus planes" : "Your plans").font(CuadraoTypography.section)
            CuadraoOrderedCollection(items: active, spanish: spanish,
                identifier: { "plan-row-\($0.kind.rawValue)-\($0.spaceID)" },
                open: { path.append($0.id) }, edit: { creation = .init(plan: $0) },
                archive: { store.archive($0.id, true) }, reorder: store.reorder) { plan in
                    PlanCard(plan: plan, space: PlanFormat.space(plan.spaceID, accounts: accounts, spanish: spanish), spanish: spanish)
                }
            NavigationLink {
                CuadraoArchivedPlans(store: store, accounts: accounts, spanish: spanish, bottomSpace: bottomSpace)
            } label: {
                Label(spanish ? "Archivados" : "Archived", systemImage: "archivebox")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary).frame(minHeight: 44)
            }.accessibilityIdentifier("plan-archives")
            if active.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text(spanish ? "¿Qué tienes en mente?" : "What do you have in mind?").font(CuadraoTypography.section)
                    Text(spanish ? "Un viaje, un respiro, llegar a fin de mes con más espacio." : "A trip, a little breathing room, a month with more left over.")
                        .font(.subheadline).foregroundStyle(.secondary)
                    PlanPrimaryButton(title: spanish ? "Crear mi primer plan" : "Make my first plan", symbol: "plus") {
                        creation = .init(plan: newPlan)
                    }
                }.padding(24).background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 26))
            }
        }
    }

}

private struct CuadraoArchivedPlans: View {
    let store: CuadraoPlanPreview
    let accounts: CuadraoAccountsPreview
    let spanish: Bool
    let bottomSpace: CGFloat
    var body: some View {
        List {
            if store.plans.filter(\.archived).isEmpty {
                ContentUnavailableView(spanish ? "Nada archivado" : "Nothing archived", systemImage: "archivebox",
                    description: Text(spanish ? "Tus planes pueden descansar aquí. Siempre podrás retomarlos." : "Plans can rest here. You can always pick them back up."))
                    .listRowSeparator(.hidden)
            }
            ForEach(store.plans.filter(\.archived)) { plan in
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(plan.name)
                        Text(PlanFormat.space(plan.spaceID, accounts: accounts, spanish: spanish)).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button(spanish ? "Retomar" : "Restore") { store.archive(plan.id, false) }.buttonStyle(.bordered)
                }
            }
        }.navigationTitle(spanish ? "Archivados" : "Archived").navigationBarTitleDisplayMode(.inline)
            .toolbar(.visible, for: .navigationBar).safeAreaPadding(.bottom, bottomSpace)
    }
}

struct PlanEditorRoute: Identifiable {
    let plan: CanvasPlan
    var id: UUID { plan.id }
}
