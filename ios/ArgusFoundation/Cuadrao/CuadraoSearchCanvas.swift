import SwiftUI

/// Searches the same in-memory records as Home; no second financial data owner.
struct CuadraoSearchCanvas: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    let includeExamples: Bool
    let plans: CuadraoPlanPreview
    let groups: CuadraoGroupPreview
    let chat: CuadraoChatPreview
    let openChat: (CanvasChatThread) -> Void
    let actions: (CanvasAccountSheet) -> Void
    let record: (UUID) -> Void
    @State private var query = ""
    @State private var kind = Kind.all
    @State private var scope = Scope.all
    @State private var currency = ""
    @State private var filters = false
    @FocusState private var focused: Bool

    private typealias Kind = CanvasSearchKind
    /// Release rule (fc7650ea): Memory appears only with the enabled native memory feature
    /// and its controls. One first-release switch gates it in Search and Profile alike.
    private static var memoryEnabled: Bool { CuadraoFirstRelease.shows(.memory) }
    private var kinds: [Kind] { Kind.allCases.filter { $0 != .memory || Self.memoryEnabled } }
    private enum Scope: CaseIterable { case all, personal, household }
    private enum Route: Hashable { case account(UUID), activity(UUID), plan(UUID), group(UUID), reference(String) }

    private var availableAccounts: [CanvasAccount] {
        data.accounts.filter { account in
            !data.spaces.contains { $0.id == account.spaceID && $0.deleted }
            && (currency.isEmpty || account.currency == currency)
            && (scope == .all || (scope == .household ? account.sharedWithHousehold : !account.sharedWithHousehold))
        }
    }
    private var accounts: [CanvasAccount] {
        availableAccounts.filter { matches($0.displayName(spanish) + " " + subtitle($0)) }
    }
    private var activity: [CanvasActivity] {
        data.activity.filter { entry in
            guard let account = availableAccounts.first(where: { $0.id == entry.accountID }) else { return false }
            return matches(entry.title + " " + account.displayName(spanish) + " " + subtitle(account))
        }.sorted { $0.date > $1.date }
    }
    private var references: [CanvasSearchReference] {
        guard scope != .household else { return [] }
        let examples = includeExamples ? CanvasSearchReference.examples(spanish).filter { $0.kind == .files || ($0.kind == .memory && Self.memoryEnabled) } : []
        return (examples + chat.references(spanish))
            .filter { matches($0.title + " " + $0.detail + " " + $0.content) }
    }
    private var matchingPlans: [CanvasPlan] {
        plans.plans.filter { plan in
            planIsAvailable(plan)
            && (currency.isEmpty || plan.currency == currency)
            && (scope == .all || (scope == .household ? plan.spaceID == CanvasSpace.householdID : plan.spaceID != CanvasSpace.householdID))
            && matches(plan.name + " " + plan.kind.title(spanish) + " " + PlanFormat.space(plan.spaceID, accounts: data, spanish: spanish))
        }
    }
    private var matchingGroups: [PlanGroup] {
        guard scope == .all else { return [] }
        return groups.groups.filter {
            (currency.isEmpty || $0.currency == currency)
            && matches($0.name + " " + $0.kind.title(spanish))
        }
    }
    private var availableCurrencies: [String] {
        Array(Set(data.accounts.map(\.currency) + plans.plans.map(\.currency) + groups.groups.map(\.currency))).sorted()
    }
    private func planIsAvailable(_ plan: CanvasPlan) -> Bool {
        !data.spaces.contains { $0.id == plan.spaceID && $0.deleted }
    }
    private var count: Int {
        (kind == .all || kind == .accounts ? accounts.count : 0)
        + (kind == .all || kind == .activity ? activity.count : 0)
        + references.filter { kind == .all || kind == $0.kind }.count
        + (kind == .all || kind == .plans ? matchingPlans.count + matchingGroups.count : 0)
    }
    private var filterCount: Int { (scope == .all ? 0 : 1) + (currency.isEmpty ? 0 : 1) }

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    if count == 0 {
                        emptyState.padding(.top, 36)
                    }
                    if (kind == .all || kind == .accounts) && !accounts.isEmpty {
                        heading(title(.accounts), count: accounts.count)
                        ForEach(accounts) { account in
                            NavigationLink(value: Route.account(account.id)) {
                                resultRow(account.displayName(spanish), detail: subtitle(account), accountKind: account.kind)
                            }.buttonStyle(.plain)
                            Divider().foregroundStyle(WelcomePalette.separator)
                        }
                    }
                    if (kind == .all || kind == .activity) && !activity.isEmpty {
                        heading(title(.activity), count: activity.count)
                        ForEach(activity) { entry in
                            if let account = data.account(entry.accountID) {
                                NavigationLink(value: Route.activity(entry.id)) {
                                    resultRow(entry.title, detail: account.displayName(spanish) + " · " + account.currency + " "
                                        + (entry.income ? "+" : "−") + CanvasMoney.format(entry.amount, currency: account.currency),
                                        symbol: entry.income ? "arrow.down.left" : nil, category: entry.income ? nil : entry.category)
                                }.buttonStyle(.plain).accessibilityIdentifier("cuadrao.search.activity.\(entry.id)")
                                Divider().foregroundStyle(WelcomePalette.separator)
                            }
                        }
                    }
                    if (kind == .all || kind == .plans) && (!matchingPlans.isEmpty || !matchingGroups.isEmpty) {
                        heading(title(.plans), count: matchingPlans.count + matchingGroups.count)
                        ForEach(matchingPlans) { plan in
                            NavigationLink(value: Route.plan(plan.id)) {
                                resultRow(plan.name, detail: [plan.kind.title(spanish),
                                    PlanFormat.space(plan.spaceID, accounts: data, spanish: spanish),
                                    plan.archived ? (spanish ? "Archivado" : "Archived") : nil].compactMap { $0 }.joined(separator: " · "), symbol: plan.look.symbol)
                            }.buttonStyle(.plain).accessibilityIdentifier("cuadrao.search.plan.\(plan.id)")
                            Divider()
                        }
                        ForEach(matchingGroups) { group in
                            NavigationLink(value: Route.group(group.id)) {
                                resultRow(group.name, detail: [group.kind.title(spanish), group.currency,
                                    group.archived ? (spanish ? "Archivado" : "Archived") : nil].compactMap { $0 }.joined(separator: " · "), symbol: group.look.symbol)
                            }.buttonStyle(.plain).accessibilityIdentifier("cuadrao.search.group.\(group.id)")
                            Divider()
                        }
                    }
                    ForEach([Kind.chats, .files, .memory].filter { kinds.contains($0) }, id: \.self) { section in
                        let rows = references.filter { $0.kind == section }
                        if (kind == .all || kind == section) && !rows.isEmpty {
                            heading(title(section), count: rows.count)
                            ForEach(rows) { item in
                                if item.kind == .chats, let thread = chat.threads.first(where: { $0.id == item.id }) {
                                    Button { focused = false; openChat(thread) } label: {
                                        resultRow(item.title, detail: item.detail, date: thread.lastMessageDate, symbol: "bubble.left")
                                    }.buttonStyle(.plain)
                                } else {
                                    NavigationLink(value: Route.reference(item.id)) {
                                        resultRow(item.title, detail: item.detail, symbol: item.kind == .memory ? "brain" : "doc")
                                    }.buttonStyle(.plain)
                                }
                                Divider()
                            }
                        }
                    }
                }.padding(.horizontal, 24).padding(.bottom, 24)
            }.scrollDismissesKeyboard(.interactively)
            .cuadraoScrollBar(edge: .top) {
                VStack(alignment: .leading, spacing: 18) {
                    searchField
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 24) {
                            ForEach(kinds, id: \.self) { value in
                                Button { kind = value; focused = false } label: {
                                    Text(title(value)).font(.subheadline)
                                        .foregroundStyle(kind == value ? Color.primary : .secondary)
                                        .frame(minHeight: 44)
                                        .overlay(alignment: .bottom) {
                                            Rectangle().fill(kind == value ? WelcomePalette.pine : .clear).frame(height: 2)
                                        }
                                }.buttonStyle(.plain)
                                    .accessibilityAddTraits(kind == value ? .isSelected : [])
                                    .accessibilityIdentifier("cuadrao.search.kind.\(value)")
                            }
                        }
                    }
                    if filterCount > 0 {
                        HStack {
                            Text([scope == .all ? nil : scopeTitle(scope), currency.isEmpty ? nil : currency].compactMap { $0 }.joined(separator: " · "))
                            Spacer()
                            Button(spanish ? "Quitar filtros" : "Clear filters") { scope = .all; currency = "" }
                                .frame(minHeight: 44)
                        }.font(.caption).foregroundStyle(.secondary)
                    }
                }.padding(.horizontal, 24).padding(.top, 24).padding(.bottom, 18)
                    .background(WelcomePalette.background.opacity(0.92))
            }
            .cuadraoSoftScrollEdges()
            .background(WelcomePalette.background)
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: Route.self) { route in
                switch route {
                case .account(let id):
                    CuadraoAccountCanvas(data: data, accountID: id, spanish: spanish, actions: actions, record: record)
                case .activity(let id):
                    CuadraoActivityDetail(data: data, activityID: id, spanish: spanish, actions: actions, record: record)
                case .plan(let id):
                    if let plan = plans.plan(id), planIsAvailable(plan) {
                        CuadraoPlanDetail(store: plans, accounts: data, planID: id, spanish: spanish)
                    } else {
                        ContentUnavailableView(spanish ? "Plan no disponible" : "Plan unavailable", systemImage: "calendar")
                            .toolbar(.visible, for: .navigationBar)
                    }
                case .group(let id):
                    if groups.group(id) != nil {
                        CuadraoGroupDetail(store: groups, groupID: id, spanish: spanish)
                    } else {
                        ContentUnavailableView(spanish ? "Plan no disponible" : "Plan unavailable", systemImage: "person.2")
                            .toolbar(.visible, for: .navigationBar)
                    }
                case .reference(let id):
                    if let item = references.first(where: { $0.id == id }) {
                        CuadraoSearchReferenceDetail(item: item, spanish: spanish,
                            source: item.kind == .memory ? CanvasSearchReference.examples(spanish).first { $0.id == "chat-cd" } : nil)
                    }
                }
            }
            .sheet(isPresented: $filters) { filterSheet }
        }.toolbar(.hidden, for: .tabBar)
    }

    private var emptyState: some View {
        ContentUnavailableView {
            Label(query.isEmpty && filterCount == 0 ? emptyTitle : (spanish ? "Sin resultados" : "No results"), systemImage: "magnifyingglass")
        } description: {
            Text(query.isEmpty && filterCount == 0 ? emptyDetail : (spanish ? "Prueba otro nombre o cambia los filtros." : "Try another name or change the filters."))
        } actions: {
            if !query.isEmpty {
                Button(spanish ? "Borrar búsqueda" : "Clear search") { query = "" }
                    .accessibilityIdentifier("cuadrao.search.clear")
            }
            if filterCount > 0 {
                Button(spanish ? "Restablecer filtros" : "Reset filters") { scope = .all; currency = "" }
                    .accessibilityIdentifier("cuadrao.search.reset")
            }
            if kind != .all {
                Button(spanish ? "Buscar en todo" : "Search everything") { kind = .all }
                    .accessibilityIdentifier("cuadrao.search.everything")
            }
        }
    }
    private var emptyTitle: String {
        switch kind {
        case .all: spanish ? "Tu información, aquí" : "Your information, here"
        case .accounts: spanish ? "Sin cuentas todavía" : "No accounts yet"
        case .activity: spanish ? "Sin movimientos todavía" : "No activity yet"
        case .plans: spanish ? "Sin planes todavía" : "No plans yet"
        case .chats: spanish ? "Sin chats todavía" : "No chats yet"
        case .files: spanish ? "Sin archivos todavía" : "No files yet"
        case .memory: spanish ? "Sin recuerdos todavía" : "No memories yet"
        }
    }
    private var emptyDetail: String {
        switch kind {
        case .all: spanish ? "Busca cuentas, movimientos, planes y conversaciones." : "Search accounts, activity, plans and conversations."
        case .accounts: spanish ? "Añade una cuenta desde Inicio para encontrarla aquí." : "Add an account from Home to find it here."
        case .activity: spanish ? "Los movimientos que registres en tus cuentas aparecerán aquí." : "Activity recorded in your accounts will appear here."
        case .plans: spanish ? "Crea una meta, un presupuesto o un plan de deuda en Plan." : "Create a goal, budget or debt plan in Plan."
        case .chats: spanish ? "Tus conversaciones guardadas aparecerán aquí." : "Your saved conversations will appear here."
        case .files: spanish ? "Los archivos disponibles aparecerán aquí." : "Available files will appear here."
        case .memory: spanish ? "El contexto que confirmes aparecerá aquí." : "Context you confirm will appear here."
        }
    }

    private var searchField: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass").foregroundStyle(.secondary).accessibilityHidden(true)
            TextField(spanish ? "Buscar" : "Search", text: $query)
                .focused($focused).autocorrectionDisabled().textInputAutocapitalization(.never)
                .submitLabel(.search).onSubmit { focused = false }
                .accessibilityIdentifier("cuadrao.search.query")
            if !query.isEmpty {
                Button { query = "" } label: { Image(systemName: "xmark.circle.fill").frame(width: 44, height: 44) }
                    .foregroundStyle(.secondary).accessibilityLabel(spanish ? "Borrar búsqueda" : "Clear search")
            }
            Button { focused = false; filters = true } label: {
                HStack(spacing: 4) {
                    Image(systemName: "slider.horizontal.3")
                    if filterCount > 0 { Text(String(filterCount)).font(.caption) }
                }.frame(minWidth: 44, minHeight: 48)
            }.accessibilityIdentifier("cuadrao.search.filters").accessibilityLabel(spanish ? "Filtros, \(filterCount) activos" : "Filters, \(filterCount) active")
        }.overlay(alignment: .bottom) { Rectangle().fill(WelcomePalette.separator).frame(height: 1) }
    }

    private var filterSheet: some View {
        NavigationStack {
            Form {
                Picker(spanish ? "Incluir" : "Include", selection: $scope) {
                    ForEach(Scope.allCases, id: \.self) { value in Text(scopeTitle(value)).tag(value) }
                }
                Picker(spanish ? "Moneda" : "Currency", selection: $currency) {
                    Text(spanish ? "Todas" : "All").tag("")
                    ForEach(availableCurrencies, id: \.self) { Text($0).tag($0) }
                }
                Section {
                    Button(spanish ? "Restablecer filtros" : "Reset filters") { scope = .all; currency = "" }
                } footer: {
                    Text(spanish ? "Solo yo incluye lo que no has compartido. Hogar incluye las cuentas compartidas y sus movimientos. Chats y archivos siguen siendo privados. Los planes en grupo aparecen en Todo. La moneda filtra cuentas, movimientos y planes."
                         : "Only me includes what you haven't shared. Household includes shared accounts and their activity. Chats and files remain private. Group plans appear in All. Currency filters accounts, activity and plans.")
                }
            }.navigationTitle(spanish ? "Filtros" : "Filters").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(spanish ? "Listo" : "Done") { filters = false } } }
        }.presentationDetents([.medium, .large]).presentationDragIndicator(.visible)
    }

    private func heading(_ title: String, count: Int) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(title).font(CuadraoTypography.section)
            Text(String(count)).font(.caption).foregroundStyle(.secondary)
        }.padding(.top, 20).padding(.bottom, 10).accessibilityAddTraits(.isHeader)
    }
    private func resultRow(_ title: String, detail: String, date: Date? = nil, symbol: String? = nil, accountKind: CanvasAccountKind? = nil, category: CanvasExpenseCategory? = nil) -> some View {
        HStack(spacing: 16) {
            if let accountKind { CanvasAccountIcon(kind: accountKind) }
            else if let category { CuadraoExpenseCategoryIcon(category: category) }
            else if let symbol {
                Image(systemName: symbol).font(.body).foregroundStyle(WelcomePalette.pine)
                    .frame(width: 42, height: 42).background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 13)).accessibilityHidden(true)
            }
            VStack(alignment: .leading, spacing: 6) {
                Text(title).font(CuadraoTypography.action)
                Text(detail).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            if let date { CuadraoChatDate(date: date, spanish: spanish) }
            else { Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary).accessibilityHidden(true) }
        }.frame(minHeight: 62).padding(.vertical, 8).contentShape(Rectangle())
    }
    private func matches(_ text: String) -> Bool {
        let needle = query.trimmingCharacters(in: .whitespacesAndNewlines)
        return needle.isEmpty || text.range(of: needle, options: [.caseInsensitive, .diacriticInsensitive]) != nil
    }
    private func subtitle(_ account: CanvasAccount) -> String {
        let space = data.spaces.first { $0.id == account.spaceID }
        return [account.kind.title(spanish), account.currency,
                account.sharedWithHousehold ? (spanish ? "Hogar" : "Household") : space?.title(spanish),
                account.archived ? (spanish ? "Archivada" : "Archived") : nil].compactMap { $0 }.joined(separator: " · ")
    }
    private func title(_ kind: Kind) -> String { kind.title(spanish) }
    private func scopeTitle(_ scope: Scope) -> String {
        switch scope {
        case .all: spanish ? "Todo" : "All"
        case .personal: spanish ? "Solo yo" : "Only me"
        case .household: spanish ? "Hogar" : "Household"
        }
    }
}
