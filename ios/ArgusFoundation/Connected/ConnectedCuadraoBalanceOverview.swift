import SwiftUI
import ArgusSession

struct ConnectedCuadraoBalanceOverview: View {
    let home: FinancialHome
    let spanish: Bool
    var space = "Personal"
    @EnvironmentObject private var auth: ProfileAuthModel
    @State private var chosenCurrency: String?
    @State private var expanded = false
    private var currencies: [FinancialCurrencySummary] {
        CurrencyPresentation.ordered(home.currencies, primary: auth.profile?.currency, currency: { $0.currency })
    }
    private var summary: FinancialCurrencySummary? {
        currencies.first { $0.currency == chosenCurrency } ?? currencies.first
    }

    var body: some View {
        if let summary {
            ConnectedBalanceReading(summary: summary, currencies: currencies.map(\.currency),
                spanish: spanish, timeZone: home.period?.timeZone ?? TimeZone.current.identifier,
                chooseCurrency: { chosenCurrency = $0 }, expand: { expanded = true })
                .fullScreenCover(isPresented: $expanded) {
                    ConnectedCuadraoInsights(summary: summary, spanish: spanish, space: space,
                        timeZone: home.period?.timeZone ?? TimeZone.current.identifier)
                }
        }
    }
}

private struct ConnectedBalanceReading: View {
    let summary: FinancialCurrencySummary
    let currencies: [String]
    let spanish: Bool
    let timeZone: String
    var expanded = false
    var chooseCurrency: (String) -> Void = { _ in }
    var expand: () -> Void = {}
    @Environment(\.locale) private var locale

    var body: some View {
        let value = ConnectedBalanceSummary(summary: summary)
        VStack(alignment: .leading, spacing: 12) {
            CuadraoBalanceAmount(amount: value.balance(locale: locale) ?? "—", currency: summary.currency,
                currencies: currencies, spanish: spanish, expanded: expanded,
                amountIdentifier: expanded ? "home-chart-amount" : "home.netWorth." + summary.currency,
                chooseCurrency: chooseCurrency, expand: expand)
            Text(summary.unknownAccounts > 0
                 ? (spanish ? "Balance parcial" : "Partial balance")
                 : (spanish ? "Balance neto" : "Net balance"))
                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                .accessibilityIdentifier("home-chart-date")
            if expanded, let asOf = summary.asOf {
                Text(AccountPresentation.date(asOf, zone: timeZone, locale: locale))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            if summary.unknownAccounts > 0 {
                Text(verbatim: String(format: NSLocalizedString("loop.home.unknownCount", comment: ""), summary.unknownAccounts))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            CuadraoChartState(title: spanish ? "Tu balance, a tu ritmo" : "Your balance, at your pace",
                detail: value.known
                    ? (spanish ? "Puedes ver tu balance actual. El historial aún no está disponible."
                        : "You can see your current balance. History is not available yet.")
                    : (spanish ? "Los balances que registres darán forma a este espacio."
                        : "Your recorded balances will give this space its shape."))
                .accessibilityIdentifier("home-chart-empty")
        }
    }
}

private struct ConnectedCuadraoInsights: View {
    let summary: FinancialCurrencySummary
    let spanish: Bool
    let space: String
    let timeZone: String
    @State private var range: CanvasHistoryRange = .month
    @State private var periodOffset = 0
    @State private var distribution = false
    @State private var activity = false
    @State private var selectedGroup: String?
    @Environment(\.locale) private var locale

    var body: some View {
        NavigationStack {
            CuadraoHomeInsightsLayout(spanish: spanish, range: $range, periodOffset: $periodOffset,
                distribution: $distribution, activity: $activity, oldestOffset: { _ in 0 }) { _ in
                    if activity {
                        VStack(alignment: .leading, spacing: 20) {
                            CuadraoSpendingReading(currency: summary.currency, amount: CuadraoMissingCoverage.amount(spanish),
                                caption: spanish ? "Gastos registrados" : "Recorded spending")
                            CuadraoChartState(title: CuadraoMissingCoverage.title(spanish), detail: CuadraoMissingCoverage.detail(spanish))
                                .accessibilityElement(children: .contain).accessibilityIdentifier("home-spending-chart")
                        }
                    } else if distribution {
                        allocation
                    } else {
                        ConnectedBalanceReading(summary: summary, currencies: [summary.currency], spanish: spanish,
                            timeZone: timeZone, expanded: true)
                    }
                }.modifier(CuadraoHomeInsightsChrome(title: space, spanish: spanish))
        }.foregroundStyle(WelcomePalette.ink).tint(WelcomePalette.pine)
    }

    private var allocation: some View {
        let value = ConnectedBalanceSummary(summary: summary)
        let groups = value.components.map { component in
            let fraction = value.fraction(component)
            return CuadraoDistributionGroup(id: component.rawValue,
                title: String(localized: String.LocalizationValue(component.titleKey), locale: locale),
                amount: value.amount(value.minor(component), locale: locale),
                percentage: fraction.formatted(.percent.precision(.fractionLength(1)).locale(locale)),
                fraction: fraction, color: component == .cash ? WelcomePalette.sunshine : WelcomePalette.overlap)
        }
        return CuadraoDistributionContent(currency: summary.currency, spanish: spanish,
            balanceTitle: balanceTitle, balance: value.balance(locale: locale) ?? "—",
            partial: summary.unknownAccounts > 0, assets: value.amount(summary.assetsMinor, locale: locale),
            groups: groups, deductions: value.deductions.map { value.amount($0, locale: locale) },
            selectedGroup: $selectedGroup) { _ in EmptyView() } deductionRows: { EmptyView() }
    }

    private var balanceTitle: String {
        let title = spanish ? "Balance neto actual" : "Current net balance"
        guard let asOf = summary.asOf else { return title }
        return title + " · " + AccountPresentation.date(asOf, zone: timeZone, locale: locale)
    }
}
