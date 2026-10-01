import SwiftUI
import ArgusSession

/// Cuadrao Home chrome bound to tip accounts + financial loop.
struct ConnectedCuadraoHome: View {
    @ObservedObject var loop: FinancialLoopModel
    @ObservedObject var accounts: AccountsModel
    @ObservedObject private var plan: FinancialPlanModel
    @Binding var tab: CuadraoTab
    @Binding var accountPath: [UUID]
    let navigationScroll: CuadraoNavigationScroll
    let showUpdates: () -> Void

    @AppStorage("cuadrao.design.home-section-order") private var homeOrder = CuadraoHomeSection.defaultOrder
    @Environment(\.locale) private var locale
    @State private var sheet: HomeSheet?
    @State private var choosingAccount = false
    @State private var actionAccount: FinancialAccount?

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private var activeAccounts: [FinancialAccount] { accounts.accounts.filter { !$0.archived } }
    private var archivedAccounts: [FinancialAccount] { accounts.accounts.filter(\.archived) }

    private enum HomeSheet: Identifiable {
        case customize, archived, options
        var id: String {
            switch self {
            case .customize: "customize"
            case .archived: "archived"
            case .options: "options"
            }
        }
    }

    init(loop: FinancialLoopModel, accounts: AccountsModel, tab: Binding<CuadraoTab>,
         accountPath: Binding<[UUID]>, navigationScroll: CuadraoNavigationScroll, showUpdates: @escaping () -> Void) {
        self.loop = loop
        self.accounts = accounts
        self.plan = loop.plan
        self._tab = tab
        self._accountPath = accountPath
        self.navigationScroll = navigationScroll
        self.showUpdates = showUpdates
    }

    var body: some View {
        NavigationStack(path: $accountPath) {
            ScrollView {
                VStack(alignment: .leading, spacing: 36) {
                    VStack(alignment: .leading, spacing: 18) {
                        header
                        Text(spanish ? "Personal" : "Personal")
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(.secondary)
                    }
                    if loop.pendingConfirmation != nil {
                        pendingBanner
                    }
                    if let recoveryError = loop.recoveryErrorKey {
                        Text(LocalizedStringKey(recoveryError)).foregroundStyle(.secondary)
                    }
                    ForEach(CuadraoHomeSection.decode(homeOrder)) { section in
                        homeSection(section)
                    }
                    if !activeAccounts.isEmpty {
                        Button { sheet = .customize } label: {
                            Label(spanish ? "Ordenar Inicio" : "Reorder Home", systemImage: "slider.horizontal.3")
                                .font(.subheadline).frame(maxWidth: .infinity, minHeight: 44)
                        }.foregroundStyle(.secondary).accessibilityIdentifier("customize-home")
                    }
                    if plan.loading { ProgressView("accounts.loading") }
                    if let error = plan.errorKey {
                        Text(LocalizedStringKey(error)).foregroundStyle(.secondary)
                        Button("accounts.retry") { Task { await loop.refresh() } }.frame(minHeight: 44)
                    }
                }
                .padding(.horizontal, 24).padding(.top, 28).padding(.bottom, 32)
            }
            .modifier(CuadraoNavigationScrollObserver(scroll: navigationScroll,
                enabled: tab == .home && sheet == nil && accountPath.isEmpty))
            .safeAreaPadding(.bottom, 80)
            .background(Color.white)
            .navigationTitle("").navigationBarTitleDisplayMode(.inline)
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: UUID.self) { id in
                if let account = accounts.accounts.first(where: { $0.id == id }) ?? accounts.selected {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {
                            AccountDetailView(account: account, model: accounts, loop: loop)
                        }.padding(24)
                    }
                    .background(Color.white)
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar(.visible, for: .navigationBar)
                }
            }
        }
        .task(id: accounts.identity?.revision) { await accounts.load(); await loop.refresh() }
        .onChange(of: accounts.accounts) { _, _ in Task { await loop.refresh() } }
        .onChange(of: accountPath) { _, path in
            if path.isEmpty, accounts.selectedID != nil { accounts.back() }
        }
        .refreshable { await accounts.load(); await loop.refresh() }
        .confirmationDialog("loop.chooseAccount", isPresented: $choosingAccount, titleVisibility: .visible) {
            ForEach(activeAccounts) { account in
                Button(account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: "")) {
                    loop.record(account)
                }
            }
        }
        .sheet(item: $sheet) { item in modal(item) }
        .confirmationDialog(
            actionAccount.map { $0.nickname ?? NSLocalizedString("accounts.type." + $0.type, comment: "") } ?? "",
            isPresented: Binding(get: { actionAccount != nil }, set: { if !$0 { actionAccount = nil } }),
            titleVisibility: .visible
        ) {
            if let account = actionAccount {
                Button(spanish ? "Cambiar nombre" : "Rename account") {
                    accounts.edit(account); actionAccount = nil
                }
                Button(spanish ? "Añadir movimiento" : "Add transaction") {
                    loop.record(account); actionAccount = nil
                }
                if account.archived {
                    Button(spanish ? "Restaurar" : "Restore") {
                        Task { await accounts.archive(account) }; actionAccount = nil
                    }
                } else {
                    Button(spanish ? "Archivar" : "Archive", role: .destructive) {
                        Task { await accounts.archive(account) }; actionAccount = nil
                    }
                }
                Button("accounts.cancel", role: .cancel) { actionAccount = nil }
            }
        }
    }

    private var header: some View {
        HStack {
            CuadraoBrand()
            Spacer()
            Button(action: showUpdates) {
                Image("CuadraoNotifications").frame(width: 44, height: 44)
            }
            .accessibilityLabel(spanish ? "Novedades" : "Updates")
        }
    }

    private var pendingBanner: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(LocalizedStringKey(loop.pendingTitle)).font(.body)
            Text("loop.pending.body").font(.caption).foregroundStyle(.secondary)
            Button("loop.pending.retry") { Task { await loop.retryPending() } }
                .buttonStyle(PillButtonStyle()).disabled(loop.recovering)
                .accessibilityIdentifier("loop.pending.retry")
        }.padding(16).overlay(RoundedRectangle(cornerRadius: 14).stroke(Color(white: 0.85)))
    }

    @ViewBuilder private func homeSection(_ section: CuadraoHomeSection) -> some View {
        switch section {
        case .overview:
            if let home = loop.home, !home.currencies.isEmpty, !activeAccounts.isEmpty {
                overview(home)
            }
        case .upcoming:
            if !activeAccounts.isEmpty {
                FinancialComingUpView(model: plan, viewPlan: { tab = .plan })
            }
        case .accounts:
            accountsSection
        case .activity:
            if let home = loop.home, !home.recentActivity.isEmpty {
                activity(home)
            }
        }
    }

    private func overview(_ home: FinancialHome) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(spanish ? "Tu panorama." : "Your overview.")
                .font(.system(.largeTitle, design: .serif))
                .fixedSize(horizontal: false, vertical: true)
            ForEach(home.currencies, id: \.currency) { summary in
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 6) {
                        Text("loop.home.netWorth")
                        Text(verbatim: "· " + summary.currency)
                    }.font(.subheadline).foregroundStyle(.secondary)
                    if summary.knownAccounts > 0 {
                        Text(verbatim: money(summary.netWorthMinor, summary))
                            .font(.system(size: 38, weight: .medium, design: .rounded))
                            .monospacedDigit()
                            .lineLimit(1).minimumScaleFactor(0.6)
                            .accessibilityIdentifier("home.netWorth." + summary.currency)
                    } else {
                        Text("accounts.unknown").font(.title2)
                    }
                    if summary.knownAccounts > 0 {
                        Text("loop.home.source").font(.footnote).foregroundStyle(.secondary)
                        summaryRow("loop.home.cash", value: money(summary.cashMinor, summary))
                        if summary.otherAssetsMinor != "0" {
                            summaryRow("loop.home.other", value: money(summary.otherAssetsMinor, summary))
                        }
                        summaryRow("loop.home.debt", value: money(summary.debtsMinor, summary))
                    }
                    if summary.unknownAccounts > 0 {
                        Text(verbatim: String(format: NSLocalizedString("loop.home.unknownCount", comment: ""), summary.unknownAccounts))
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private var accountsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            if !activeAccounts.isEmpty || !archivedAccounts.isEmpty {
                HStack(spacing: 0) {
                    Text(spanish ? "Cuentas" : "Accounts")
                        .font(.system(.title2, design: .serif))
                        .accessibilityAddTraits(.isHeader)
                    Spacer()
                    Button { accounts.create() } label: { Image(systemName: "plus").frame(width: 44, height: 44) }
                        .accessibilityLabel(spanish ? "Añadir cuenta" : "Add account")
                        .accessibilityIdentifier("accounts.add")
                    Button { sheet = .options } label: { Image(systemName: "ellipsis").frame(width: 44, height: 44) }
                        .accessibilityLabel(spanish ? "Opciones de cuentas" : "Account options")
                }
            }
            ForEach(activeAccounts) { account in
                Button {
                    Task {
                        await accounts.open(account)
                        await loop.open(account)
                        accountPath.append(account.id)
                    }
                } label: {
                    ConnectedAccountRow(account: account, spanish: spanish)
                }
                .buttonStyle(.plain)
                .simultaneousGesture(LongPressGesture(minimumDuration: 0.45).onEnded { _ in
                    actionAccount = account
                })
                .contextMenu {
                    Button(spanish ? "Cambiar nombre" : "Rename account") { accounts.edit(account) }
                    Button(spanish ? "Añadir movimiento" : "Add transaction") { loop.record(account) }
                    Button(spanish ? "Archivar" : "Archive", role: .destructive) {
                        Task { await accounts.archive(account) }
                    }
                }
                .accessibilityIdentifier("accounts.row.\(account.id)")
                .overlay(alignment: .bottom) { Divider().padding(.leading, 54) }
            }
            if activeAccounts.isEmpty {
                personalEmpty
            }
        }
    }

    private var personalEmpty: some View {
        VStack(alignment: .leading, spacing: 28) {
            Image(systemName: "wallet.bifold")
                .font(.system(size: 28, weight: .light)).foregroundStyle(WelcomePalette.pine)
                .frame(width: 60, height: 60)
                .background(WelcomePalette.sage, in: RoundedRectangle(cornerRadius: 18))
                .accessibilityHidden(true)
            RegistrationHeading(
                title: spanish ? "Empieza con una cuenta." : "Start with one account.",
                detail: spanish ? "Tu banco, tu efectivo o tus ahorros. Tú eliges por dónde empezar."
                    : "Your bank, cash or savings. Choose where to begin.")
            RegistrationButton(title: spanish ? "Añadir cuenta" : "Add account") {
                accounts.create()
            }
            .accessibilityIdentifier("accounts.add")
        }.padding(.top, 16).frame(maxWidth: .infinity, alignment: .leading)
    }

    private func activity(_ home: FinancialHome) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(spanish ? "Movimientos" : "Activity")
                    .font(.system(.title2, design: .serif))
                    .accessibilityAddTraits(.isHeader)
                Spacer()
                Button {
                    if activeAccounts.count == 1, let account = activeAccounts.first {
                        loop.record(account)
                    } else {
                        choosingAccount = true
                    }
                } label: {
                    Image(systemName: "plus").frame(width: 44, height: 44)
                }
                .accessibilityLabel(spanish ? "Añadir movimiento" : "Add activity")
                .disabled(activeAccounts.isEmpty || loop.pendingConfirmation != nil)
                .accessibilityIdentifier("home.record")
            }
            ForEach(home.recentActivity, id: \.recordId) { entry in
                if let account = accounts.accounts.first(where: { $0.id == entry.accountId }) {
                    Button {
                        Task {
                            await accounts.open(account)
                            await loop.open(account)
                            accountPath.append(account.id)
                        }
                    } label: {
                        FinancialActivityRow(activity: entry, currency: account.currency)
                    }.buttonStyle(.plain)
                }
            }
        }
    }

    @ViewBuilder private func modal(_ item: HomeSheet) -> some View {
        switch item {
        case .customize:
            CuadraoHomeLayoutSheet(savedOrder: $homeOrder, spanish: spanish)
        case .options:
            VStack(alignment: .leading, spacing: 8) {
                Text(spanish ? "Cuentas" : "Accounts").font(.title3.weight(.medium)).padding(.bottom, 12)
                CanvasActionRow(title: spanish ? "Cuentas archivadas" : "Archived accounts", symbol: "archivebox") {
                    sheet = .archived
                }
            }.padding(28).presentationDetents([.height(200)]).presentationDragIndicator(.visible)
        case .archived:
            ConnectedArchivedAccounts(accounts: accounts, spanish: spanish)
        }
    }

    private func summaryRow(_ title: LocalizedStringKey, value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(verbatim: value).monospacedDigit()
        }.font(.caption)
    }

    private func money(_ minor: String, _ summary: FinancialCurrencySummary) -> String {
        summary.currency + " " + AccountPresentation.amount(AccountPresentation.decimal(minor, digits: summary.currencyFractionDigits), locale: locale)
    }
}

private enum ConnectedAccountKind {
    static func map(_ type: String) -> CanvasAccountKind {
        switch type {
        case "cash": .cash
        case "checking": .checking
        case "savings": .savings
        case "investment": .investment
        case "credit_card": .card
        case "other_debt": .loan
        case "property": .property
        case "vehicle": .vehicle
        case "other_asset": .asset
        default: .checking
        }
    }
}

private struct ConnectedAccountRow: View {
    let account: FinancialAccount
    let spanish: Bool
    @Environment(\.locale) private var locale

    var body: some View {
        HStack(spacing: 12) {
            CanvasAccountIcon(kind: ConnectedAccountKind.map(account.type))
                .frame(width: 42, height: 42)
                .background(WelcomePalette.sage.opacity(0.65), in: RoundedRectangle(cornerRadius: 13))
            VStack(alignment: .leading, spacing: 5) {
                Text(account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: ""))
                    .font(.body.weight(.medium))
                Text(LocalizedStringKey("accounts.type." + account.type))
                    .font(.caption).foregroundStyle(.secondary)
                if account.isOptionalAsset {
                    Text("assets.whole").font(.caption2).foregroundStyle(.secondary)
                }
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 5) {
                if let amount = account.balance.amount {
                    Text(verbatim: AccountPresentation.amount(amount, locale: locale))
                        .font(.subheadline.weight(.medium)).monospacedDigit()
                } else {
                    Text("accounts.unknown").font(.subheadline.weight(.medium))
                }
                Text(verbatim: account.currency).font(.caption).foregroundStyle(.secondary)
            }
        }.padding(.vertical, 12).contentShape(Rectangle())
    }
}

private struct ConnectedArchivedAccounts: View {
    @ObservedObject var accounts: AccountsModel
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss

    private var archived: [FinancialAccount] { accounts.accounts.filter(\.archived) }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text(spanish ? "Sus balances e historial se conservan." : "Balances and history are kept.")
                        .font(.subheadline).foregroundStyle(.secondary)
                    if archived.isEmpty {
                        ContentUnavailableView(spanish ? "No hay cuentas archivadas" : "No archived accounts",
                                               systemImage: "archivebox")
                    }
                    ForEach(archived) { account in
                        VStack(alignment: .leading, spacing: 0) {
                            ConnectedAccountRow(account: account, spanish: spanish)
                            CanvasActionRow(title: spanish ? "Restaurar" : "Restore", symbol: "arrow.uturn.backward") {
                                Task { await accounts.archive(account) }
                            }.foregroundStyle(WelcomePalette.pine)
                            Divider()
                        }
                    }
                }.padding(24)
            }.background(Color.white)
                .navigationTitle(spanish ? "Cuentas archivadas" : "Archived accounts")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button(spanish ? "Listo" : "Done") { dismiss() }
                    }
                }
        }.tint(WelcomePalette.pine)
    }
}
