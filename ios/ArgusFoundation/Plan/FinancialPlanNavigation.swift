import SwiftUI

enum FinancialPlanHost: Equatable {
    case home, plan, search

    init(_ origin: FinancialGoalNavigation.Origin) {
        switch origin {
        case .home: self = .home
        case .plan, .planOverview: self = .plan
        case .search: self = .search
        }
    }

    init(_ origin: FinancialBudgetNavigation.Origin) {
        switch origin {
        case .home: self = .home
        case .plan, .planOverview: self = .plan
        case .search: self = .search
        }
    }

    init(_ origin: FinancialDebtNavigation.Origin) {
        switch origin {
        case .home, .account: self = .home
        case .plan, .planOverview: self = .plan
        case .search, .searchAccount: self = .search
        }
    }

    var tab: CuadraoTab {
        switch self { case .home: .home; case .plan: .plan; case .search: .search }
    }
}

extension View {
    @ViewBuilder func financialPlanDestinations(loop: FinancialLoopModel, search: FinancialSearchModel?,
        host: FinancialPlanHost, accountDetailPresented: Bool = false, enabled: Bool = true) -> some View {
        if enabled {
            modifier(FinancialPlanDestinations(goals: loop.goals, budgets: loop.budgets,
                loop: loop, search: search, host: host))
                .modifier(FinancialDebtDestination(model: loop.debts, loop: loop, search: search,
                    host: host, accountDetailPresented: accountDetailPresented))
        } else { self }
    }

    @ViewBuilder func financialAccountDebtDestination(loop: FinancialLoopModel, search: FinancialSearchModel?, accountID: UUID,
        origin: FinancialDebtNavigation.Origin, enabled: Bool) -> some View {
        if enabled {
            modifier(FinancialDebtDestination(model: loop.debts, loop: loop, search: search,
                host: FinancialPlanHost(origin), accountID: accountID, accountOrigin: origin))
        } else { self }
    }
}

private struct FinancialPlanDestinations: ViewModifier {
    @ObservedObject var goals: FinancialGoalModel
    @ObservedObject var budgets: FinancialBudgetModel
    let loop: FinancialLoopModel
    let search: FinancialSearchModel?
    let host: FinancialPlanHost

    func body(content: Content) -> some View {
        content
            .navigationDestination(isPresented: goalPresented) {
                FinancialGoalDetail(model: goals, loop: loop, nativeNavigation: true, close: closeGoal)
                    .accessibilityElement(children: .contain).accessibilityIdentifier("goal.detail")
            }
            .navigationDestination(isPresented: budgetPresented) {
                FinancialBudgetDetailView(model: budgets, loop: loop, nativeNavigation: true, close: closeBudget)
                    .accessibilityElement(children: .contain).accessibilityIdentifier("budget.detail")
            }
    }

    private var goalPresented: Binding<Bool> {
        let captured = goals.navigation
        return Binding(get: { goals.navigation.map { FinancialPlanHost($0.origin) == host } ?? false }, set: { presented in
            guard !presented, let captured, FinancialPlanHost(captured.origin) == host,
                  let current = goals.navigation, current.goalID == captured.goalID,
                  current.origin == captured.origin else { return }
            closeGoal()
        })
    }

    private var budgetPresented: Binding<Bool> {
        let captured = budgets.navigation
        return Binding(get: { budgets.navigation.map { FinancialPlanHost($0.origin) == host } ?? false }, set: { presented in
            guard !presented, let captured, FinancialPlanHost(captured.origin) == host,
                  let current = budgets.navigation, current.budgetID == captured.budgetID,
                  current.origin == captured.origin else { return }
            closeBudget()
        })
    }

    private func closeGoal() { goals.close(); Task { await search?.refresh() } }
    private func closeBudget() { budgets.close(); Task { await search?.refresh() } }
}

private struct FinancialDebtDestination: ViewModifier {
    @ObservedObject var model: FinancialDebtModel
    let loop: FinancialLoopModel
    let search: FinancialSearchModel?
    let host: FinancialPlanHost
    var accountDetailPresented = false
    var accountID: UUID?
    var accountOrigin: FinancialDebtNavigation.Origin?

    private func accepts(_ route: FinancialDebtNavigation) -> Bool {
        if let accountID {
            let debt = model.detail?.debt ?? loop.plan.projection?.debts?.first { $0.id == route.debtID }?.debt
            return route.origin == accountOrigin && debt?.debtAccountId == accountID
        }
        let fromAccount = route.origin == .account || route.origin == .searchAccount
        return FinancialPlanHost(route.origin) == host && !(fromAccount && accountDetailPresented)
    }

    func body(content: Content) -> some View {
        content.navigationDestination(isPresented: presented) {
            FinancialDebtDetail(model: model, loop: loop, nativeNavigation: true, close: close)
                .accessibilityElement(children: .contain).accessibilityIdentifier("debt.detail")
        }
    }

    private var presented: Binding<Bool> {
        let captured = model.navigation
        return Binding(get: { model.navigation.map(accepts) ?? false }, set: { presented in
            guard !presented, let captured, accepts(captured), let current = model.navigation,
                  current.debtID == captured.debtID, current.origin == captured.origin else { return }
            close()
        })
    }

    private func close() { model.close(); Task { await search?.refresh() } }
}

struct FinancialPlanNavigationState<Content: View>: View {
    @ObservedObject private var goals: FinancialGoalModel
    @ObservedObject private var budgets: FinancialBudgetModel
    @ObservedObject private var debts: FinancialDebtModel
    let loop: FinancialLoopModel
    @Binding var tab: CuadraoTab
    @ViewBuilder let content: (Bool) -> Content

    init(loop: FinancialLoopModel, tab: Binding<CuadraoTab>, @ViewBuilder content: @escaping (Bool) -> Content) {
        self.loop = loop
        goals = loop.goals; budgets = loop.budgets; debts = loop.debts
        _tab = tab
        self.content = content
    }

    private enum Route: Equatable {
        case goal(UUID, FinancialGoalNavigation.Origin)
        case budget(UUID, FinancialBudgetNavigation.Origin)
        case debt(UUID, FinancialDebtNavigation.Origin)

        var host: FinancialPlanHost {
            switch self {
            case .goal(_, let origin): FinancialPlanHost(origin)
            case .budget(_, let origin): FinancialPlanHost(origin)
            case .debt(_, let origin): FinancialPlanHost(origin)
            }
        }

        var section: PlanSection? {
            switch self {
            case .goal(_, .plan): .goals
            case .budget(_, .plan): .budgets
            case .debt(_, .plan): .debts
            case .goal(_, .planOverview), .budget(_, .planOverview), .debt(_, .planOverview): .overview
            default: nil
            }
        }
    }

    private var routes: [Route] {
        var result: [Route] = []
        if let route = goals.navigation { result.append(.goal(route.goalID, route.origin)) }
        if let route = budgets.navigation { result.append(.budget(route.budgetID, route.origin)) }
        if let route = debts.navigation { result.append(.debt(route.debtID, route.origin)) }
        return result
    }

    private var restoredRoute: Route? { routes.count == 1 ? routes.first : nil }

    var body: some View {
        content(!routes.contains { $0.host.tab == tab })
            .onChange(of: restoredRoute, initial: true) { _, route in
                guard let route else { return }
                if let section = route.section { loop.plan.section = section }
                tab = route.host.tab
            }
    }
}
