import SwiftUI
import ArgusSession

struct FinancialSearchDestination: View {
    @EnvironmentObject private var auth: ProfileAuthModel
    let active: Bool
    let showProfile: () -> Void
    var nativePlanNavigation = false
    var detailChanged: (Bool) -> Void = { _ in }
    var body: some View {
        if auth.state == .authenticated, let model = auth.financialSearch, let accounts = auth.accounts, let loop = auth.financialLoop {
            FinancialSearchView(model: model, accounts: accounts, loop: loop, active: active, nativePlanNavigation: nativePlanNavigation, detailChanged: detailChanged)
        } else {
            VStack(alignment: .leading, spacing: 24) {
                Text("search.title").font(CuadraoTypography.screen)
                Text("search.gate").foregroundStyle(.secondary)
                Button("auth.signIn", action: showProfile).buttonStyle(PillButtonStyle())
                Spacer()
            }.padding(24)
        }
    }
}

struct FinancialSearchView: View {
    @ObservedObject var model: FinancialSearchModel
    @ObservedObject var accounts: AccountsModel
    @ObservedObject var loop: FinancialLoopModel
    @ObservedObject private var goals: FinancialGoalModel
    @ObservedObject private var budgets: FinancialBudgetModel
    @ObservedObject private var debts: FinancialDebtModel
    let active: Bool
    var nativePlanNavigation = false
    var detailChanged: (Bool) -> Void = { _ in }
    @Environment(\.locale) private var locale
    @StateObject private var scroll = FinancialScrollOffset()
    @State private var unavailableKind: CanvasSearchKind?
    @State private var showsProgress = false
    @FocusState private var focused: Bool

    init(model: FinancialSearchModel, accounts: AccountsModel, loop: FinancialLoopModel,
         active: Bool, nativePlanNavigation: Bool = false, detailChanged: @escaping (Bool) -> Void = { _ in }) {
        self.model = model; self.accounts = accounts; self.loop = loop
        goals = loop.goals; budgets = loop.budgets; debts = loop.debts
        self.active = active; self.nativePlanNavigation = nativePlanNavigation; self.detailChanged = detailChanged
    }

    private var hasPlanDetail: Bool {
        goals.navigation.map { FinancialPlanHost($0.origin) == .search } == true ||
            budgets.navigation.map { FinancialPlanHost($0.origin) == .search } == true ||
            debts.navigation.map { FinancialPlanHost($0.origin) == .search } == true
    }

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private var inputKey: String {
        (model.ownerID ?? "") + "|" + model.origin.query + "|" + model.origin.scope.rawValue
            + "|" + (model.origin.currency ?? "") + "|" + String(describing: unavailableKind)
    }
    private var currencies: [String] {
        Array(Set(accounts.accounts.map(\.currency) + model.items.map(\.currency) + [model.origin.currency].compactMap { $0 })).sorted()
    }
    private var query: Binding<String> { Binding(get: { model.origin.query }, set: { model.update(query: $0) }) }
    private var kind: Binding<CanvasSearchKind> {
        Binding(get: { unavailableKind ?? Self.perspective(model.origin.scope) }, set: select)
    }
    private static func perspective(_ scope: FinancialSearchScope) -> CanvasSearchKind {
        switch scope { case .all: .all; case .accounts: .accounts; case .activity: .activity; case .plans: .plans }
    }
    private static func section(_ kind: FinancialSearchKind) -> CanvasSearchKind {
        switch kind {
        case .account: .accounts
        case .activity: .activity
        case .expectation, .budget, .goal, .debt: .plans
        }
    }
    private var busy: Bool { unavailableKind == nil && (model.loading || model.opening) }
    private var filterCount: Int {
        unavailableKind == nil && model.origin.currency != nil ? 1 : 0
    }
    private var filterSummary: String { model.origin.currency ?? "" }

    var body: some View {
        NavigationStack {
            CuadraoSearchContent(query: query, kind: kind,
                kinds: CanvasSearchKind.allCases.filter { $0 != .memory }, spanish: spanish,
                filterCount: filterCount, filterSummary: filterSummary, clearFilters: clearFilters,
                focused: $focused, accessibility: .connected, loading: showsProgress,
                refresh: { if unavailableKind == nil { await model.refresh() } }, eagerRows: true) {
                FinancialScrollProbe(controller: scroll).frame(height: 0)
                results
            } filters: {
                filterControls
            }
            .simultaneousGesture(DragGesture(minimumDistance: 1).onChanged { _ in model.userScrolled() })
            .onPreferenceChange(FinancialScrollRowFrames.self) { rememberFrames($0) }
            .onChange(of: model.restoration) { _, restoration in
                guard !hasPlanDetail, let restoration else { return }
                Task { @MainActor in
                    await Task.yield()
                    guard model.restoration?.id == restoration.id else { return }
                    scroll.view?.layoutIfNeeded()
                    if let frame = scroll.frames[restoration.anchor],
                       scroll.restore(restoration, currentRowOffset: frame.minY) {
                        model.restored(restoration.id)
                    }
                }
            }
            .navigationDestination(isPresented: Binding(
                get: { model.destination != nil },
                set: { if !$0 { Task { await model.back() } } })) {
                    destination
                }
            .financialPlanDestinations(loop: loop, search: model, host: .search,
                accountDetailPresented: model.destination != nil, enabled: nativePlanNavigation)
        }
        .task(id: inputKey) {
            guard active, unavailableKind == nil else { return }
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            await model.activate()
        }
        .task(id: busy) {
            guard busy else { showsProgress = false; return }
            try? await Task.sleep(for: .milliseconds(400))
            if !Task.isCancelled { showsProgress = true }
        }
        .onChange(of: inputKey) { _, _ in
            guard let view = scroll.view else { return }
            view.setContentOffset(CGPoint(x: view.contentOffset.x, y: -view.adjustedContentInset.top), animated: false)
        }
        .onChange(of: active) { _, active in
            if active, unavailableKind == nil { Task { await model.activate() } }
            else { focused = false }
        }
        .onChange(of: model.destination != nil || hasPlanDetail, initial: true) { _, showing in detailChanged(showing) }
        .onChange(of: model.ownerID) { _, _ in unavailableKind = nil }
        .toolbar(.hidden, for: .tabBar)
    }

    @ViewBuilder private var results: some View {
        if let unavailableKind {
            CuadraoSearchEmptyState(query: query, kind: kind, spanish: spanish,
                filterCount: 0, clearFilters: clearFilters,
                title: unavailableKind.title(spanish), detail: unavailableDetail(unavailableKind), accessibility: .connected)
                .padding(.top, 36)
        } else {
            if let error = model.destinationError {
                Text(LocalizedStringKey(error)).padding(.vertical, 12).accessibilityIdentifier("search.destination.error")
                Button("action.close") { model.dismissError() }.frame(minHeight: 44)
            }
            if let error = model.errorKey {
                Text(LocalizedStringKey(error)).padding(.vertical, 12).accessibilityIdentifier("search.error")
                Button("accounts.retry") { Task { await model.refresh() } }.frame(minHeight: 44).accessibilityIdentifier("search.retry")
            } else if model.items.isEmpty && !model.loading {
                CuadraoSearchEmptyState(query: query, kind: kind, spanish: spanish,
                    filterCount: filterCount, clearFilters: clearFilters,
                    detail: kind.wrappedValue == .all && model.origin.query.isEmpty && filterCount == 0
                        ? (spanish ? "Busca cuentas, movimientos y planes." : "Search accounts, activity and plans.") : nil,
                    accessibility: .connected)
                    .padding(.top, 36)
            }
            ForEach([CanvasSearchKind.accounts, .activity, .plans], id: \.self) { section in
                let rows = model.items.filter { Self.section($0.kind) == section }
                if !rows.isEmpty {
                    CuadraoSearchHeading(title: section.title(spanish), count: rows.count)
                    ForEach(rows) { hit in
                        Button { focused = false; Task { await model.open(hit, accounts: accounts, loop: loop) } } label: {
                            FinancialSearchRow(hit: hit, accounts: accounts.accounts)
                        }.buttonStyle(.plain).disabled(model.opening)
                            .id(hit.id).accessibilityIdentifier("search.row." + hit.id)
                            .financialScrollAnchor(hit.id, in: "search.viewport")
                        Divider().foregroundStyle(WelcomePalette.separator)
                    }
                }
            }
            if model.cursor != nil {
                Button("loop.more") { Task { await model.more() } }.frame(minHeight: 48)
                    .disabled(model.loading).accessibilityIdentifier("search.more")
            }
        }
    }

    @ViewBuilder private var filterControls: some View {
        if unavailableKind == nil {
            Picker(spanish ? "Moneda" : "Currency", selection: Binding(
                get: { model.origin.currency }, set: { model.update(currency: .some($0)) })) {
                    Text(spanish ? "Todas" : "All").tag(nil as String?)
                    ForEach(currencies, id: \.self) { Text($0).tag(Optional($0)) }
                }.accessibilityIdentifier("search.currency")
            Section {
                Button(spanish ? "Restablecer filtros" : "Reset filters", action: clearFilters)
            } footer: {
                Text(spanish ? "Busca en tus registros personales. La moneda filtra cuentas, movimientos y planes."
                    : "Search your personal records. Currency filters accounts, activity and plans.")
            }
        } else if let unavailableKind {
            Text(unavailableDetail(unavailableKind)).foregroundStyle(.secondary)
        }
    }

    private var destination: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                switch model.destination {
                case .account(let id):
                    if let account = accounts.accounts.first(where: { $0.id == id }) {
                        AccountDetailView(account: account, model: accounts, loop: loop, debtOrigin: .searchAccount, nativePlanNavigation: nativePlanNavigation, search: model)
                    } else { Text("search.destination.unavailable") }
                case .activity(let id):
                    FinancialActivityDetailView(loop: loop, activityID: id, accounts: accounts.accounts,
                        openAccount: { id in
                            guard let account = accounts.accounts.first(where: { $0.id == id }) else { return }
                            Task { await model.open(.account(account), accounts: accounts, loop: loop) }
                        }) { loop.correct($0) }
                case nil: EmptyView()
                }
            }.padding(24).padding(.bottom, 32)
        }.background(WelcomePalette.background).accessibilityIdentifier("search.detail")
            .navigationTitle("").navigationBarTitleDisplayMode(.inline)
            .toolbar(.visible, for: .navigationBar)
    }

    private func select(_ selected: CanvasSearchKind) {
        switch selected {
        case .all: unavailableKind = nil; model.update(scope: .all)
        case .accounts: unavailableKind = nil; model.update(scope: .accounts)
        case .activity: unavailableKind = nil; model.update(scope: .activity)
        case .plans: unavailableKind = nil; model.update(scope: .plans)
        case .chats, .files, .memory: unavailableKind = selected; model.invalidate()
        }
    }
    private func clearFilters() { model.update(currency: .some(nil)) }
    private func unavailableDetail(_ kind: CanvasSearchKind) -> String {
        switch kind {
        case .chats: spanish ? "Tus chats aún no están disponibles en esta búsqueda." : "Your chats are not available in this search yet."
        case .files: spanish ? "Tus archivos aún no están disponibles en esta búsqueda." : "Your files are not available in this search yet."
        default: spanish ? "La memoria aún no está disponible en esta búsqueda." : "Memory is not available in this search yet."
        }
    }
    private func rememberFrames(_ frames: [String: CGRect]) {
        scroll.frames = frames
        guard !hasPlanDetail else { return }
        if let restoration = model.restoration {
            if let frame = frames[restoration.anchor], scroll.restore(restoration, currentRowOffset: frame.minY) {
                model.restored(restoration.id)
            }
            return
        }
        guard active, unavailableKind == nil,
              let row = frames.filter({ $0.value.maxY > 0 }).min(by: { $0.value.minY < $1.value.minY }) else { return }
        model.remember(anchor: row.key, offset: row.value.minY)
    }
}

struct FinancialSearchRow: View {
    let hit: FinancialSearchHit
    let accounts: [FinancialAccount]
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        CuadraoSearchResultRow(title: title, detail: detail, spanish: spanish,
            symbol: symbol, accountKind: artwork, category: category)
            .accessibilityElement(children: .combine)
    }
    private var title: String {
        switch hit {
        case .account(let account): ConnectedAccountPresentation.title(account, spanish: spanish)
        case .activity(let activity, _): activity.note ?? NSLocalizedString("loop.kind." + activity.kind.rawValue, comment: "")
        case .expectation(let expectation): expectation.title
        case .budget(let budget): budget.name
        case .goal(let goal): goal.goal.name
        case .debt(let debt): debt.debt.name
        }
    }
    private var detail: String {
        var parts: [String] = []
        if case .account(let account) = hit {
            parts.append(ConnectedAccountPresentation.artwork(account.type)?.title(spanish) ?? account.type)
        }
        if case .activity(let activity, _) = hit {
            let names = activity.legs.sorted { $0.balanceMovementMinor < $1.balanceMovementMinor }
                .compactMap { leg in accounts.first { $0.id == leg.accountId } }
                .map { ConnectedAccountPresentation.title($0, spanish: spanish) }
            if !names.isEmpty { parts.append(names.joined(separator: " → ")) }
        }
        switch hit {
        case .expectation(let expectation): parts.append(NSLocalizedString("plan.kind." + expectation.kind.rawValue, comment: ""))
        case .budget, .goal, .debt: parts.append(NSLocalizedString("search.filter." + hit.kind.rawValue, comment: ""))
        default: break
        }
        let amount = hit.amount.map { AccountPresentation.amount($0, locale: locale) }
            ?? NSLocalizedString("accounts.unknown", comment: "")
        let amountLabel = hit.currency + " " + activitySign + amount
        if case .goal = hit { parts.append(NSLocalizedString("goal.target", comment: "") + " · " + amountLabel) }
        else { parts.append(amountLabel) }
        if hit.archived { parts.append(NSLocalizedString("accounts.archived", comment: "")) }
        return parts.joined(separator: " · ")
    }
    private var activitySign: String {
        guard case .activity(let activity, _) = hit, activity.amount != nil, activity.legs.count == 1,
              let leg = activity.legs.first else { return "" }
        return FinancialActivityPresentation.sign(for: leg.balanceMovementMinor)
    }
    private var artwork: CanvasAccountKind? {
        if case .account(let account) = hit { return ConnectedAccountPresentation.artwork(account.type) }
        return nil
    }
    private var category: CanvasExpenseCategory? {
        if case .activity(let activity, _) = hit, activity.kind == .expense, let category = activity.categoryId {
            return .fromRecordedCategory(category)
        }
        return nil
    }
    private var symbol: String {
        switch hit {
        case .account(let account): AccountPresentation.symbol(account.type)
        case .activity(let activity, _): FinancialActivityPresentation.symbol(for: activity.kind.rawValue)
        case .expectation: "calendar"
        case .budget: "chart.bar"
        case .goal: "target"
        case .debt: "creditcard"
        }
    }
}

struct FinancialDomainPresenter: View {
    @ObservedObject var accounts: AccountsModel
    @ObservedObject var plan: FinancialPlanModel
    @ObservedObject var loop: FinancialLoopModel
    let search: FinancialSearchModel?
    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .sheet(item: $loop.assetEditor, onDismiss: refreshSearch) { editor in FinancialAssetForm(model: editor, accounts: accounts).tint(ArgusStyle.ink).foregroundStyle(ArgusStyle.ink) }
            .sheet(item: $accounts.draft, onDismiss: refreshSearch) { draft in ConnectedAccountSheet(model: accounts, mode: draft.mode) }
            .sheet(item: $plan.draft, onDismiss: refreshSearch) { draft in FinancialExpectationForm(model: plan, draft: draft, loop: loop).tint(ArgusStyle.ink).foregroundStyle(ArgusStyle.ink) }
            // One presenter so Home Upcoming and Plan open the same occurrence sheet.
            .sheet(item: $plan.selectedOccurrence, onDismiss: { plan.occurrenceDismissed(); refreshSearch() }) { occurrence in
                FinancialOccurrenceView(model: plan, loop: loop, occurrence: occurrence)
            }
    }
    private func refreshSearch() { Task { await search?.refresh() } }
}
