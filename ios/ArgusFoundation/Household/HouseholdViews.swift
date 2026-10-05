import SwiftUI
import ArgusSession

struct HouseholdDestinationRouter<Personal: View>: View {
    @ObservedObject var model: HouseholdModel
    let tab: AppDestination
    let active: Bool
    @Binding var destination: AppDestination
    var navigationScroll: CuadraoNavigationScroll?
    var showUpdates: (() -> Void)?
    @ViewBuilder let personal: () -> Personal

    var body: some View {
        if model.active, tab != .argus {
            HouseholdConnectedDestination(model: model, tab: tab, active: active,
                destination: $destination, navigationScroll: navigationScroll, showUpdates: showUpdates)
        } else { personal() }
    }
}

struct HouseholdConnectedDestination: View {
    @ObservedObject var model: HouseholdModel
    let tab: AppDestination
    let active: Bool
    @Binding var destination: AppDestination
    var navigationScroll: CuadraoNavigationScroll?
    var showUpdates: (() -> Void)?
    @ObservedObject private var plan: HouseholdPlanModel

    init(model: HouseholdModel, tab: AppDestination, active: Bool,
         destination: Binding<AppDestination>, navigationScroll: CuadraoNavigationScroll? = nil,
         showUpdates: (() -> Void)? = nil) {
        self.model = model; self.tab = tab; self.active = active
        _destination = destination; self.navigationScroll = navigationScroll
        self.showUpdates = showUpdates; plan = model.plan
    }

    var body: some View {
        if active {
            NavigationStack {
                content
                    .accessibilityElement(children: .contain)
                    .accessibilityIdentifier("screen." + tab.rawValue)
                    .toolbar(.hidden, for: .navigationBar)
                    .navigationDestination(isPresented: Binding(
                        get: { model.detail != nil && tab != .plan },
                        set: { if !$0 { model.back() } })) {
                        ConnectedHouseholdAccountDetail(model: model)
                    }
                    .navigationDestination(isPresented: Binding(
                        get: { plan.openedRef != nil && plan.origin.rawValue == tab.rawValue },
                        set: { if !$0 { plan.back() } })) {
                        ScrollView {
                            HouseholdPlanDetailView(model: plan)
                                .padding(24).padding(.bottom, 32)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .background(WelcomePalette.background)
                        .accessibilityIdentifier("sharedPlan.detail")
                        .toolbar(.hidden, for: .navigationBar)
                        .refreshable { await model.refresh() }
                    }
            }.tint(WelcomePalette.pine).foregroundStyle(WelcomePalette.ink)
                .background(WelcomePalette.background)
        } else { Color.clear }
    }

    @ViewBuilder private var content: some View {
        switch tab {
        case .home:
            ConnectedHouseholdHome(model: model, destination: $destination,
                navigationScroll: navigationScroll, showUpdates: showUpdates)
        case .plan:
            ConnectedHouseholdPlan(model: model)
        case .search:
            ConnectedHouseholdSearch(model: model)
        case .accounts:
            ScrollView {
                ConnectedHouseholdAccounts(model: model).padding(24).padding(.bottom, 80)
            }.background(WelcomePalette.background).refreshable { await model.foreground() }
        case .argus:
            EmptyView()
        }
    }
}

enum HouseholdMoney {
    static func minor(_ amount: Int64, currency: String, digits: Int) -> String {
        currency + " " + AccountPresentation.amount(AccountPresentation.decimal(amount, digits: digits), locale: .current)
    }
}

struct HouseholdPresenter: View {
    @ObservedObject var model: HouseholdModel
    @EnvironmentObject private var auth: ProfileAuthModel
    @Environment(\.scenePhase) private var phase
    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .task(id: model.identity?.revision) { await model.refresh() }
            .onChange(of: phase) { _, phase in if phase == .active { Task { await model.foreground() } } }
            .sheet(isPresented: Binding(get: { model.isAvailable && model.showManagement }, set: { model.showManagement = $0 })) { HouseholdManagement(model: model, accounts: auth.accounts).tint(WelcomePalette.pine).foregroundStyle(WelcomePalette.ink) }
            .sheet(item: Binding(get: { model.isAvailable ? model.editor : nil }, set: { model.editor = $0 })) { HouseholdActivityEditorView(model: $0).tint(WelcomePalette.pine).foregroundStyle(WelcomePalette.ink) }
    }
}
