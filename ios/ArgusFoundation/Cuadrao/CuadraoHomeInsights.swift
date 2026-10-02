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
    @Environment(\.dismiss) private var dismiss
    private var periodLabel: some View {
        Text(range.periodLabel(spanish: spanish, offset: periodOffset))
            .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true).accessibilityIdentifier("home-insight-period")
    }
    private var metricChoice: some View {
        CuadraoChoiceMenu(title: spanish ? "Vista" : "View", selection: $activity,
            values: [false, true], valueTitle: { value in value ? (spanish ? "Actividad" : "Activity") : "Balance" })
            .accessibilityIdentifier("home-insight-metric")
    }
    private var controls: CuadraoInsightControls { CuadraoInsightControls(range: $range, distribution: $distribution, spanish: spanish, activity: activity) }
    private var expenses: [CanvasActivity] {
        CanvasSpendingHistory.expenses(data.visibleActivity, accounts: data.scopedAccounts, currency: currency)
    }
    private var history: [CanvasBalancePoint] { CanvasBalanceHistory.points(accounts: accounts, observations: data.balanceObservations, now: .now) }
    private var oldest: Int { activity ? CanvasSpendingHistory.oldestOffset(expenses, range: range) : range.oldestOffset(history) }
    private var snapshot: [CanvasAccount] {
        guard periodOffset < 0 else { return accounts }
        guard let date = range.points(history, offset: periodOffset).last?.date else { return [] }
        return CanvasBalanceHistory.snapshot(accounts: accounts, observations: data.balanceObservations, at: date)
    }
    private func movePeriod(_ direction: Int) { periodOffset = min(0, max(oldest, periodOffset + direction)) }
    private var distributionSwipe: some Gesture {
        DragGesture(minimumDistance: 25).onEnded { value in
            guard abs(value.translation.width) > abs(value.translation.height) * 1.4 else { return }
            movePeriod(value.translation.width > 0 ? -1 : 1)
        }
    }
    var body: some View {
        NavigationStack(path: $accountPath) {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    ViewThatFits(in: .horizontal) {
                        HStack(alignment: .firstTextBaseline, spacing: 12) {
                            periodLabel
                            Spacer(minLength: 8)
                            metricChoice
                        }
                        VStack(alignment: .leading, spacing: 8) {
                            periodLabel
                            metricChoice.frame(maxWidth: .infinity, alignment: .trailing)
                        }
                    }
                    if activity {
                        CuadraoSpendingChart(expenses: expenses, currency: currency, spanish: spanish,
                            distribution: distribution, range: range, periodOffset: $periodOffset, controls: controls)
                    } else if distribution {
                        CuadraoHomeDistribution(accounts: snapshot, currency: currency, spanish: spanish, controls: controls, historical: periodOffset < 0,
                            asOf: periodOffset == 0 ? nil : range.points(history, offset: periodOffset).last?.date)
                            .contentShape(Rectangle()).simultaneousGesture(distributionSwipe)
                            .accessibilityAction(named: Text(spanish ? "Período anterior" : "Previous period")) { movePeriod(-1) }
                            .accessibilityAction(named: Text(spanish ? "Período siguiente" : "Next period")) { movePeriod(1) }
                    } else {
                        CuadraoHomeBalanceChart(accounts: accounts, observations: data.balanceObservations, currency: currency,
                            currencies: [currency], spanish: spanish, shared: shared, chooseCurrency: { _ in }, expanded: true, controls: controls,
                            range: $range, periodOffset: $periodOffset)
                    }
                }.padding(.horizontal, 24).padding(.top, 16).padding(.bottom, 32)
            }.accessibilityIdentifier("home-insights-content").background(WelcomePalette.background)
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
        }.sheet(item: $accountSheet) { selection in
            CuadraoAccountModal(data: data, selection: selection, spanish: spanish,
                show: { accountSheet = $0 }, archived: { _ in
                    accountSheet = nil; accountPath = []
                })
        }.onChange(of: range) { _, _ in periodOffset = 0 }
            .onChange(of: activity) { _, _ in periodOffset = max(oldest, periodOffset) }
            .tint(WelcomePalette.pine).foregroundStyle(WelcomePalette.ink)
    }
}
