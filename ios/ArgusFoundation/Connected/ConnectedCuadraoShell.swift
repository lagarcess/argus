import SwiftUI

/// Connected Cuadrao shell: Home hosts accounts; no Accounts tab.
struct ConnectedCuadraoShell: View {
    @Binding var appearance: AppearancePreference
    @EnvironmentObject private var auth: ProfileAuthModel
    @Environment(\.locale) private var locale
    @State private var tab: CuadraoTab = .home
    @State private var destination: AppDestination = .home
    @State private var sheet: FoundationSheet?
    @State private var navigationScroll = CuadraoNavigationScroll()
    @State private var homePath: [ConnectedHomeRoute] = []
    @State private var profilePath: [CuadraoProfileDestination] = []
    @State private var avatar: CuadraoAvatarSelection = .none

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        ZStack {
            ForEach(CuadraoTab.allCases) { item in
                tabContent(item)
                    .opacity(tab == item ? 1 : 0)
                    .allowsHitTesting(tab == item)
                    .accessibilityHidden(tab != item)
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            if (homePath.isEmpty || tab != .home) && (profilePath.isEmpty || tab != .profile) {
                CuadraoNavigationBar(selection: $tab, compact: tab == .home && navigationScroll.compact, spanish: spanish, avatar: avatar, profileName: auth.profile?.displayName ?? "")
                    .padding(.horizontal, 20)
                    .frame(height: 64, alignment: .bottom)
                    .padding(.bottom, 8)
            }
        }
        .background { if let household = auth.household { HouseholdPresenter(model: household) } }
        .background { if let household = auth.household { HouseholdPlanPresenter(model: household.plan) } }
        .financialBudgetBackground(auth.financialLoop?.budgets)
        .financialGoalBackground(auth.financialLoop?.goals)
        .financialDebtBackground(auth.financialLoop?.debts)
        .overlay {
            if let loop = auth.financialLoop {
                FinancialBudgetPresenter(model: loop.budgets, loop: loop, destination: $destination, search: auth.financialSearch)
            }
        }
        .overlay {
            if let loop = auth.financialLoop {
                FinancialGoalPresenter(model: loop.goals, loop: loop, destination: $destination, search: auth.financialSearch)
            }
        }
        .overlay {
            if let loop = auth.financialLoop {
                FinancialDebtPresenter(model: loop.debts, loop: loop, destination: $destination, search: auth.financialSearch)
            }
        }
        .background {
            if let loop = auth.financialLoop { FinancialEditorPresenter(loop: loop, appearance: appearance) }
        }
        .background {
            if let accounts = auth.accounts, let loop = auth.financialLoop {
                FinancialDomainPresenter(accounts: accounts, plan: loop.plan, loop: loop, search: auth.financialSearch)
            }
        }
        .sheet(item: $sheet) { selected in
            if selected == .updates {
                NavigationStack {
                    ReleaseUpdatesInbox(state: .unavailable, spanish: spanish)
                        .toolbar {
                            ToolbarItem(placement: .confirmationAction) {
                                Button(spanish ? "Listo" : "Done") { sheet = nil }.accessibilityIdentifier("sheet.close")
                            }
                        }
                }.preferredColorScheme(appearance.colorScheme)
            } else {
                FoundationSheetView(sheet: selected, appearance: $appearance)
                    .preferredColorScheme(appearance.colorScheme)
                    .tint(ArgusStyle.ink)
                    .foregroundStyle(ArgusStyle.ink)
            }
        }
        .tint(WelcomePalette.pine)
        .foregroundStyle(Color(white: 0.08))
        .background(Color.white.ignoresSafeArea())
        .onChange(of: destination) { _, value in mapDestination(value) }
        .onChange(of: tab) { _, value in mapTab(value) }
        .onChange(of: auth.profile?.id) { _, _ in avatar = .none; profilePath = [] }
    }

    @ViewBuilder private func tabContent(_ item: CuadraoTab) -> some View {
        if item != .profile, let household = auth.household {
            HouseholdDestinationRouter(model: household, tab: householdTab(item), active: tab == item, destination: $destination) { personalTabContent(item) }
        } else { personalTabContent(item) }
    }

    @ViewBuilder private func personalTabContent(_ item: CuadraoTab) -> some View {
        switch item {
        case .home:
            if let loop = auth.financialLoop, let accounts = auth.accounts {
                ConnectedCuadraoHome(loop: loop, accounts: accounts, tab: $tab, homePath: $homePath,
                                     navigationScroll: navigationScroll, showUpdates: { sheet = .updates })
            } else {
                ProgressView("accounts.loading")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        case .plan:
            NavigationStack {
                FinancialPlanDestination(showProfile: { tab = .profile })
                    .toolbar(.hidden, for: .navigationBar)
            }
        case .assistant:
            NavigationStack {
                ChatSampleView(showSample: { sheet = .sample })
                    .toolbar(.hidden, for: .navigationBar)
            }
        case .search:
            NavigationStack {
                FinancialSearchDestination(active: tab == .search, showProfile: { tab = .profile })
                    .toolbar(.hidden, for: .navigationBar)
            }
        case .profile:
            NavigationStack(path: $profilePath) {
                ConnectedCuadraoProfile(appearance: $appearance, avatar: $avatar)
            }
        }
    }

    private func householdTab(_ item: CuadraoTab) -> AppDestination {
        switch item { case .home, .profile: .home; case .plan: .plan; case .assistant: .argus; case .search: .search }
    }

    private func mapDestination(_ value: AppDestination) {
        switch value {
        case .accounts:
            tab = .home
            if let accounts = auth.accounts, let loop = auth.financialLoop {
                if let account = accounts.selected {
                    if homePath != [.account(account.id)] { homePath = [.account(account.id)] }
                    Task { await accounts.open(account); await loop.open(account) }
                } else if let id = accounts.selectedID {
                    if homePath != [.account(id)] { homePath = [.account(id)] }
                }
            }
            if destination != .home { destination = .home }
        case .plan: tab = .plan
        case .search: tab = .search
        case .home:
            tab = .home
            if !homePath.isEmpty { homePath = [] }
        case .argus: tab = .assistant
        }
    }

    private func mapTab(_ value: CuadraoTab) {
        switch value {
        case .home: if destination != .home && destination != .accounts { destination = .home }
        case .plan: destination = .plan
        case .assistant: destination = .argus
        case .search: destination = .search
        case .profile: break
        }
    }
}
