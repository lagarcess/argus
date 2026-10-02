import SwiftUI

/// Searches the same in-memory records as Home; no second financial data owner.
struct CuadraoSearchCanvas: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    let includeExamples: Bool
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
    private enum Scope: CaseIterable { case all, personal, household }
    private enum Route: Hashable { case account(UUID), activity(UUID), reference(String) }

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
        guard includeExamples, scope != .household else { return [] }
        return (CanvasSearchReference.examples(spanish).filter { $0.kind != .chats } + chat.references(spanish))
            .filter { matches($0.title + " " + $0.detail + " " + $0.content) }
    }
    private var count: Int {
        (kind == .all || kind == .accounts ? accounts.count : 0)
        + (kind == .all || kind == .activity ? activity.count : 0)
        + references.filter { kind == .all || kind == $0.kind }.count
    }
    private var filterCount: Int { (scope == .all ? 0 : 1) + (currency.isEmpty ? 0 : 1) }

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    if count == 0 {
                        ContentUnavailableView {
                            Label(spanish ? (query.isEmpty && filterCount == 0 ? "Todo empieza con una cuenta" : "Sin resultados")
                                  : (query.isEmpty && filterCount == 0 ? "Start with an account" : "No results"), systemImage: "magnifyingglass")
                        } description: {
                            Text(spanish ? (data.accounts.isEmpty ? "Las cuentas y movimientos que añadas aparecerán aquí." : "Prueba otro nombre o cambia los filtros.")
                                 : (data.accounts.isEmpty ? "Accounts and activity you add will appear here." : "Try another name or change the filters."))
                        }.padding(.top, 36)
                    }
                    if (kind == .all || kind == .accounts) && !accounts.isEmpty {
                        heading(title(.accounts), count: accounts.count)
                        ForEach(accounts) { account in
                            NavigationLink(value: Route.account(account.id)) {
                                resultRow(account.displayName(spanish), detail: subtitle(account))
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
                                        + (entry.income ? "+" : "−") + CanvasMoney.format(entry.amount, currency: account.currency))
                                }.buttonStyle(.plain)
                                Divider().foregroundStyle(WelcomePalette.separator)
                            }
                        }
                    }
                    ForEach([Kind.plans, .chats, .files, .memory], id: \.self) { section in
                        let rows = references.filter { $0.kind == section }
                        if (kind == .all || kind == section) && !rows.isEmpty {
                            heading(title(section), count: rows.count)
                            ForEach(rows) { item in
                                if item.kind == .chats, let thread = chat.threads.first(where: { $0.id == item.id }) {
                                    Button { focused = false; openChat(thread) } label: {
                                        resultRow(item.title, detail: item.detail, date: thread.lastMessageDate)
                                    }.buttonStyle(.plain)
                                } else {
                                    NavigationLink(value: Route.reference(item.id)) {
                                        resultRow(item.title, detail: item.detail)
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
                            ForEach(Kind.allCases, id: \.self) { value in
                                Button { kind = value; focused = false } label: {
                                    Text(title(value)).font(.subheadline)
                                        .foregroundStyle(kind == value ? Color.primary : .secondary)
                                        .frame(minHeight: 44)
                                        .overlay(alignment: .bottom) {
                                            Rectangle().fill(kind == value ? WelcomePalette.pine : .clear).frame(height: 2)
                                        }
                                }.buttonStyle(.plain)
                                    .accessibilityAddTraits(kind == value ? .isSelected : [])
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
                    activityDetail(id)
                case .reference(let id):
                    if let item = CanvasSearchReference.examples(spanish).first(where: { $0.id == id }) {
                        CuadraoSearchReferenceDetail(item: item, spanish: spanish,
                            source: item.kind == .memory ? CanvasSearchReference.examples(spanish).first { $0.id == "chat-cd" } : nil)
                    }
                }
            }
            .sheet(isPresented: $filters) { filterSheet }
        }.toolbar(.hidden, for: .tabBar)
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
            }.accessibilityLabel(spanish ? "Filtros, \(filterCount) activos" : "Filters, \(filterCount) active")
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
                    ForEach(Array(Set(data.accounts.map(\.currency))).sorted(), id: \.self) { Text($0).tag($0) }
                }
                Section {
                    Button(spanish ? "Restablecer filtros" : "Reset filters") { scope = .all; currency = "" }
                } footer: {
                    Text(spanish ? "Solo yo incluye lo que no has compartido. Hogar incluye las cuentas compartidas y sus movimientos. Chats, archivos y memoria siguen siendo privados. La moneda filtra solo cuentas y movimientos."
                         : "Only me includes what you haven't shared. Household includes shared accounts and their activity. Chats, files and memory remain private. Currency filters only accounts and activity.")
                }
            }.navigationTitle(spanish ? "Filtros" : "Filters").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(spanish ? "Listo" : "Done") { filters = false } } }
        }.presentationDetents([.medium, .large]).presentationDragIndicator(.visible)
    }

    @ViewBuilder private func activityDetail(_ id: UUID) -> some View {
        if let entry = data.activity.first(where: { $0.id == id }), let account = data.account(entry.accountID) {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    Text(entry.title).font(CuadraoTypography.feature)
                    Text(account.currency + " " + (entry.income ? "+" : "−") + CanvasMoney.format(entry.amount, currency: account.currency))
                        .font(CuadraoTypography.amount)
                    LabeledContent(spanish ? "Tipo" : "Type", value: entry.income ? (spanish ? "Ingreso" : "Income") : (spanish ? "Gasto" : "Expense"))
                    LabeledContent(spanish ? "Fecha" : "Date") { Text(entry.date, format: .dateTime.day().month(.wide).year()) }
                    NavigationLink(value: Route.account(account.id)) {
                        resultRow(account.displayName(spanish), detail: subtitle(account))
                    }.buttonStyle(.plain)
                }.padding(24)
            }.background(WelcomePalette.background).navigationTitle(spanish ? "Movimiento" : "Activity")
                .navigationBarTitleDisplayMode(.inline).toolbar(.visible, for: .navigationBar)
        } else {
            ContentUnavailableView(spanish ? "Movimiento no disponible" : "Activity unavailable", systemImage: "doc.text.magnifyingglass")
                .toolbar(.visible, for: .navigationBar)
        }
    }

    private func heading(_ title: String, count: Int) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(title).font(.headline)
            Text(String(count)).font(.caption).foregroundStyle(.secondary)
        }.padding(.top, 20).padding(.bottom, 10).accessibilityAddTraits(.isHeader)
    }
    private func resultRow(_ title: String, detail: String, date: Date? = nil) -> some View {
        HStack(spacing: 16) {
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
