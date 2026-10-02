import SwiftUI

struct CuadraoHomeInsights: View {
    let data: CuadraoAccountsPreview
    private var accounts: [CanvasAccount] { data.active.filter { $0.currency == currency } }
    let currency: String
    let spanish: Bool
    let space: String
    let shared: Bool
    @State private var range: CanvasHistoryRange = .month
    @State private var periodOffset = 0
    @State private var distribution = false
    @State private var activity = false
    @State private var accountPath: [UUID] = []
    @State private var tipSheet: InsightAccountSheet?
    @Environment(\.dismiss) private var dismiss

    private enum InsightAccountSheet: Identifiable {
        case actions(UUID), rename(UUID), record(UUID)
        var id: String {
            switch self {
            case .actions(let id): "actions-\(id)"
            case .rename(let id): "rename-\(id)"
            case .record(let id): "record-\(id)"
            }
        }
    }

    private func periodLabel(_ offset: Int) -> some View {
        Text(range.periodLabel(spanish: spanish, offset: offset))
            .font(CuadraoTypography.feature).foregroundStyle(WelcomePalette.ink)
            .fixedSize(horizontal: false, vertical: true).accessibilityIdentifier("home-insight-period")
    }
    private var metricChoice: some View {
        CuadraoChoiceMenu(title: spanish ? "Vista" : "View", selection: Binding(get: { activity }, set: { value in
            periodOffset = max(value ? CanvasSpendingHistory.oldestOffset(expenses, range: range) : range.oldestOffset(history), periodOffset)
            activity = value
        }),
            values: [false, true], valueTitle: { value in value ? (spanish ? "Actividad" : "Activity") : "Balance" })
            .accessibilityIdentifier("home-insight-metric")
    }
    private var controls: CuadraoInsightControls { CuadraoInsightControls(range: Binding(get: { range }, set: { periodOffset = 0; range = $0 }), distribution: $distribution, spanish: spanish, activity: activity) }
    private var expenses: [CanvasActivity] {
        CanvasSpendingHistory.expenses(data.visibleActivity, accounts: data.scopedAccounts, currency: currency)
    }
    private var history: [CanvasBalancePoint] { CanvasBalanceHistory.points(accounts: accounts, observations: data.balanceObservations, now: .now) }
    private var oldest: Int { activity ? CanvasSpendingHistory.oldestOffset(expenses, range: range) : range.oldestOffset(history) }
    private func snapshot(_ offset: Int) -> [CanvasAccount] {
        guard offset < 0 else { return accounts }
        guard let date = range.points(history, offset: offset).last?.date else { return [] }
        return CanvasBalanceHistory.snapshot(accounts: accounts, observations: data.balanceObservations, at: date)
    }
    private func movePeriod(_ direction: Int) { periodOffset = min(0, max(oldest, periodOffset + direction)) }
    @ViewBuilder private func periodContent(_ offset: Int) -> some View {
        if activity {
            CuadraoSpendingChart(expenses: expenses, coverageStart: data.spendingCoverageStart(currency: currency), currency: currency,
                spanish: spanish, distribution: distribution, range: range, periodOffset: .constant(offset))
        } else if distribution {
            CuadraoHomeDistribution(accounts: snapshot(offset), currency: currency, spanish: spanish, historical: offset < 0,
                asOf: offset == 0 ? nil : range.points(history, offset: offset).last?.date)
        } else {
            CuadraoHomeBalanceChart(accounts: accounts, observations: data.balanceObservations, currency: currency,
                currencies: [currency], spanish: spanish, shared: shared, chooseCurrency: { _ in }, expanded: true,
                range: $range, periodOffset: .constant(offset))
        }
    }
    var body: some View {
        NavigationStack(path: $accountPath) {
            VStack(spacing: 8) {
                VStack(spacing: 4) {
                    metricChoice.frame(maxWidth: .infinity, alignment: .trailing)
                    controls
                }.padding(.horizontal, 24)
                TabView(selection: $periodOffset) {
                    ForEach(Array(oldest...0), id: \.self) { offset in
                        ScrollView {
                            if abs(offset - periodOffset) <= 1 {
                                VStack(alignment: .leading, spacing: 16) {
                                    periodLabel(offset)
                                    periodContent(offset)
                                }.padding(.horizontal, 24).padding(.top, 16).padding(.bottom, 32)
                            }
                        }
                        .accessibilityIdentifier("home-insights-content")
                        .accessibilityHidden(offset != periodOffset)
                        .accessibilityAction(named: Text(spanish ? "Período anterior" : "Previous period")) { movePeriod(-1) }
                        .accessibilityAction(named: Text(spanish ? "Período siguiente" : "Next period")) { movePeriod(1) }
                        .tag(offset)
                    }
                }.tabViewStyle(.page(indexDisplayMode: .never)).id(range.rawValue + String(activity))
                    .accessibilityAction(named: Text(spanish ? "Período anterior" : "Previous period")) { movePeriod(-1) }
                    .accessibilityAction(named: Text(spanish ? "Período siguiente" : "Next period")) { movePeriod(1) }
            }.background(WelcomePalette.background)
                .navigationDestination(for: UUID.self) { id in
                    CuadraoAccountCanvas(data: data, accountID: id, spanish: spanish,
                        actions: { tipSheet = .actions($0) }, record: { tipSheet = .record($0) })
                }
                .navigationTitle(space).navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button { dismiss() } label: { Image(systemName: "xmark").frame(width: 44, height: 44) }
                            .accessibilityLabel(spanish ? "Cerrar" : "Close").accessibilityIdentifier("home-history-done")
                    }
                }
        }.sheet(item: $tipSheet) { selection in
            switch selection {
            case .actions(let id):
                if let account = data.account(id) {
                    CuadraoAccountActions(account: account, spanish: spanish,
                        rename: { tipSheet = .rename(id) },
                        record: { tipSheet = .record(id) },
                        archive: {
                            data.archive(id, true)
                            tipSheet = nil
                            accountPath = []
                        })
                }
            case .rename(let id):
                if let account = data.account(id) {
                    CuadraoRenameAccount(data: data, account: account, spanish: spanish)
                }
            case .record(let id):
                if let account = data.account(id) {
                    CuadraoTransactionCanvas(data: data, account: account, spanish: spanish)
                }
            }
        }.onChange(of: oldest) { _, value in periodOffset = max(value, periodOffset) }
            .tint(WelcomePalette.pine).foregroundStyle(WelcomePalette.ink)
    }
}
