import SwiftUI

struct CuadraoPlanCanvas: View {
    let store: CuadraoPlanPreview
    let accounts: CuadraoAccountsPreview
    let spanish: Bool
    var bottomSpace: CGFloat = 90
    @State private var path: [UUID] = []
    @State private var scope = "personal"
    @State private var filter: String?
    @State private var selectedDay: Int?
    @State private var creation: PlanEditorRoute?
    @State private var resetConfirmation = false
    @State private var showEmpty = false

    private var forecast: CanvasForecast { CanvasForecast(household: scope == "household") }
    private var active: [CanvasPlan] { store.plans.filter { !$0.archived && (filter == nil || $0.spaceID == filter) } }
    private var selectedPoint: CanvasForecastPoint? {
        guard let selectedDay else { return nil }
        return (forecast.actual + forecast.projection(daily: store.daily(for: scope)).dropFirst()).first { $0.day == selectedDay }
    }
    private var scopeName: String { PlanFormat.space(scope, accounts: accounts, spanish: spanish) }

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 30) {
                    header
                    if store.hasForecast { forecastOverview } else { forecastColdStart }
                    plans
                    PlanPreviewFootnote(spanish: spanish)
                }.padding(.horizontal, 24).padding(.top, 20).padding(.bottom, bottomSpace)
            }
            .scrollIndicators(.hidden)
            .background(WelcomePalette.background)
            .toolbar(.hidden, for: .navigationBar).toolbar(.hidden, for: .tabBar)
            .cuadraoSoftScrollEdges()
            .navigationDestination(for: UUID.self) { id in
                CuadraoPlanDetail(store: store, accounts: accounts, planID: id, spanish: spanish, bottomSpace: bottomSpace)
            }
            .sheet(item: $creation) { route in
                CuadraoPlanEditor(store: store, accounts: accounts, initial: route.plan, spanish: spanish) { id in
                    if store.plan(route.plan.id) != nil { path.append(id) }
                }
            }
            .confirmationDialog(spanish ? "¿Cambiar el escenario de vista previa?" : "Change preview scenario?", isPresented: $resetConfirmation, titleVisibility: .visible) {
                Button(spanish ? "Cambiar escenario" : "Change scenario", role: .destructive) {
                    store.resetExamples(spanish: spanish, empty: showEmpty); filter = nil
                }
            } message: {
                Text(spanish ? "Se reemplazarán solo los planes de esta vista previa." : "Only this preview's plans will be replaced.")
            }
        }.tint(WelcomePalette.pine)
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Plan").font(.system(.largeTitle, design: .serif))
                Text(spanish ? "Dale forma a lo que viene." : "Make room for what's next.")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            Spacer()
            Menu {
                NavigationLink { CuadraoArchivedPlans(store: store, accounts: accounts, spanish: spanish, bottomSpace: bottomSpace) } label: { Label(spanish ? "Archivados" : "Archived", systemImage: "archivebox") }
                Section(spanish ? "Vista previa" : "Preview") {
                    Button(spanish ? "Ver primer uso" : "See first use") { showEmpty = true; resetConfirmation = true }
                    Button(spanish ? "Restablecer ejemplos" : "Reset examples") { showEmpty = false; resetConfirmation = true }
                }
            } label: {
                Image(systemName: "ellipsis").frame(width: 44, height: 44).contentShape(Circle())
            }.accessibilityLabel(spanish ? "Opciones de Plan" : "Plan options").accessibilityIdentifier("plan-options")
            Button { creation = PlanEditorRoute(plan: newPlan) } label: {
                Image(systemName: "plus").font(.system(size: 20, weight: .medium))
                    .frame(width: 44, height: 44).background(WelcomePalette.sage, in: Circle())
            }.accessibilityLabel(spanish ? "Crear plan" : "Create plan").accessibilityIdentifier("plan-create")
        }
    }

    private var newPlan: CanvasPlan {
        CanvasPlan(name: "", spaceID: filter ?? (accounts.visibleSpaces.contains { $0.id == scope } ? scope : "personal"))
    }

    private var forecastOverview: some View {
        VStack(alignment: .leading, spacing: 16) {
            Menu {
                ForEach(accounts.visibleSpaces.filter { $0.kind == .personal || $0.kind == .household }) { space in
                    Button { scope = space.id; selectedDay = nil } label: {
                        if scope == space.id { Label(space.title(spanish), systemImage: "checkmark") }
                        else { Text(space.title(spanish)) }
                    }
                }
            } label: {
                HStack(spacing: 6) {
                    Text(spanish ? "Octubre · \(scopeName)" : "October · \(scopeName)")
                    Image(systemName: "chevron.down").font(.caption2.weight(.semibold))
                }.font(.subheadline).frame(minHeight: 36)
            }.accessibilityIdentifier("plan-forecast-scope")
            Text(spanish ? "MES DE EJEMPLO · 2026" : "EXAMPLE MONTH · 2026").font(.system(size: 10, weight: .medium)).tracking(1.2).foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 5) {
                Text(selectedPoint.map { "\($0.day) oct. · \($0.day > CanvasForecast.today ? (spanish ? "estimado" : "estimated") : (spanish ? "registrado" : "recorded"))" } ?? (store.dailyAssumptions[scope] == nil ? (spanish ? "A este ritmo, cerrarías con" : "At this pace, you'd end with") : (spanish ? "Con tu plan, cerrarías con" : "With your plan, you'd end with")))
                    .font(.subheadline).foregroundStyle(.secondary)
                Text(PlanFormat.amount(selectedPoint?.balance ?? forecast.ending(daily: store.daily(for: scope))))
                    .font(.system(size: 36, weight: .regular, design: .rounded)).monospacedDigit()
                    .contentTransition(.numericText()).minimumScaleFactor(0.65).lineLimit(1)
                    .accessibilityIdentifier("plan-month-ending")
            }
            PlanForecastChart(forecast: forecast, daily: store.daily(for: scope), spanish: spanish, selectedDay: $selectedDay)
            NavigationLink {
                CuadraoForecastPlayground(store: store, scope: scope, scopeName: scopeName, spanish: spanish, bottomSpace: bottomSpace)
            } label: {
                HStack {
                    Text(spanish ? "¿Y si cambias el ritmo?" : "What if you changed the pace?")
                    Spacer(); Image(systemName: "arrow.up.right")
                }.font(.subheadline.weight(.medium)).frame(minHeight: 44)
            }.accessibilityIdentifier("plan-explore")
        }
    }

    private var forecastColdStart: some View {
        VStack(alignment: .leading, spacing: 18) {
            PlanLandscape(look: .sunshine).frame(height: 135)
            Text(spanish ? "Lo que viene empieza aquí." : "What's next starts here.")
                .font(.system(.title, design: .serif))
            Text(spanish ? "Puedes hacer tu primer plan hoy. La proyección llegará cuando tengas movimientos e ingresos previstos." : "Make your first plan today. Your forecast will take shape with transactions and expected income.")
                .font(.subheadline).foregroundStyle(.secondary)
            Button(spanish ? "Explorar un mes de ejemplo" : "Explore an example month") {
                store.enableForecastExample()
            }.font(.subheadline.weight(.medium)).frame(minHeight: 44)
        }
    }

    private var plans: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text(spanish ? "Tus planes" : "Your plans").font(.system(.title2, design: .serif))
                Spacer()
                Menu {
                    Button(spanish ? "Todos los espacios" : "All spaces") { filter = nil }
                    ForEach(accounts.visibleSpaces) { space in Button(space.title(spanish)) { filter = space.id } }
                } label: {
                    HStack(spacing: 5) {
                        Text(filter.map { PlanFormat.space($0, accounts: accounts, spanish: spanish) } ?? (spanish ? "Todos" : "All"))
                        Image(systemName: "line.3.horizontal.decrease")
                    }.font(.caption).frame(minHeight: 44)
                }.accessibilityIdentifier("plan-space-filter")
            }
            ForEach(active) { plan in
                NavigationLink(value: plan.id) {
                    PlanCard(plan: plan, space: PlanFormat.space(plan.spaceID, accounts: accounts, spanish: spanish), spanish: spanish)
                }.buttonStyle(.plain).accessibilityIdentifier("plan-row-\(plan.kind.rawValue)-\(plan.spaceID)")
                    .contextMenu {
                        Button { creation = .init(plan: plan) } label: { Label(spanish ? "Editar" : "Edit", systemImage: "pencil") }
                        Button { store.archive(plan.id, true) } label: { Label(spanish ? "Archivar" : "Archive", systemImage: "archivebox") }
                    }
            }
            if active.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text(spanish ? "¿Qué tienes en mente?" : "What do you have in mind?").font(.system(.title2, design: .serif))
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
