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
    @State private var accountSheet: CanvasAccountSheet?
    @State private var chooseRecordingAccount = false
    @Environment(\.dismiss) private var dismiss
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
    private var oldest: Int { oldestOffset(history) }
    private func oldestOffset(_ history: @autoclosure () -> [CanvasBalancePoint]) -> Int {
        activity ? CanvasSpendingHistory.oldestOffset(expenses, range: range) : range.oldestOffset(history())
    }
    private func balancePeriod(_ offset: Int, built: CanvasBuiltBalanceHistory?) -> CanvasBalancePeriod {
        let now = Date.now
        guard let history = built?.points(on: now) else {
            return CanvasBalancePeriod(accounts: accounts, observations: data.balanceObservations, range: range, offset: offset, now: now)
        }
        return CanvasBalancePeriod(accounts: accounts, observations: data.balanceObservations, range: range, offset: offset, now: now, history: history)
    }
    private func recordFirstExpense() {
        if accounts.count == 1, let account = accounts.first { accountSheet = .record(account.id) }
        else { chooseRecordingAccount = true }
    }
    private func movePeriod(_ direction: Int) { periodOffset = min(0, max(oldest, periodOffset + direction)) }
    private func chartContext(_ offset: Int) -> CanvasChartFocus {
        CanvasChartFocus(spaceID: data.selectedSpaceID, spaceTitle: space, currency: currency,
            interval: range.interval(offset: offset), periodTitle: range.periodLabel(spanish: spanish, offset: offset),
            metric: activity ? .activity : .balance, presentation: distribution ? .distribution : .evolution)
    }
    @ViewBuilder private func periodContent(_ offset: Int, built: CanvasBuiltBalanceHistory?) -> some View {
        if activity {
            CuadraoSpendingChart(expenses: expenses, coverageStart: data.spendingCoverageStart(currency: currency), currency: currency,
                spanish: spanish, distribution: distribution, range: range, periodOffset: .constant(offset), record: accounts.isEmpty ? nil : recordFirstExpense, context: chartContext(offset))
        } else if distribution {
            let period = balancePeriod(offset, built: built)
            CuadraoHomeDistribution(accounts: period.closingAccounts, currency: currency, spanish: spanish, historical: offset < 0,
                asOf: period.closing?.date, context: chartContext(offset))
        } else {
            CuadraoHomeBalanceChart(accounts: accounts, observations: data.balanceObservations, currency: currency,
                currencies: [currency], spanish: spanish, shared: shared, chooseCurrency: { _ in }, expanded: true,
                history: built, range: $range, periodOffset: .constant(offset))
            CanvasChartAsk(context: chartContext(offset), spanish: spanish)
        }
    }
    var body: some View {
        // One history per pass feeds the page range, every live page and its period.
        let built = activity ? nil : CanvasBuiltBalanceHistory(accounts: accounts, observations: data.balanceObservations, now: .now)
        let oldest = oldestOffset(built?.points ?? history)
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
                                    periodContent(offset, built: built)
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
                        actions: { accountSheet = $0 }, record: { accountSheet = .record($0) })
                }
                .navigationTitle(space).navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button { dismiss() } label: { Image(systemName: "xmark").frame(width: 44, height: 44) }
                            .accessibilityLabel(spanish ? "Cerrar" : "Close").accessibilityIdentifier("home-history-done")
                    }
                }
        }.confirmationDialog(spanish ? "¿En qué cuenta?" : "Which account?", isPresented: $chooseRecordingAccount, titleVisibility: .visible) {
            ForEach(accounts) { account in
                Button(account.displayName(spanish)) { accountSheet = .record(account.id) }
            }
        }.sheet(item: $accountSheet) { selection in
            CuadraoAccountModal(data: data, selection: selection, spanish: spanish,
                show: { accountSheet = $0 }, archived: { _ in
                    accountSheet = nil; accountPath = []
                })
        }.onChange(of: oldest) { _, value in periodOffset = max(value, periodOffset) }
            .tint(WelcomePalette.pine).foregroundStyle(WelcomePalette.ink)
    }
}
