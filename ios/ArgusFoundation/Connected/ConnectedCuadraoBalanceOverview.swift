import SwiftUI
import ArgusSession

struct ConnectedCuadraoBalanceOverview: View {
    let home: FinancialHome
    let spanish: Bool
    @Environment(\.locale) private var locale
    @State private var chosenCurrency: String?
    @State private var expanded = false
    private var summary: FinancialCurrencySummary? {
        home.currencies.first { $0.currency == chosenCurrency } ?? home.currencies.first
    }

    var body: some View {
        if let summary {
            content(summary, expanded: false)
                .fullScreenCover(isPresented: $expanded) {
                    NavigationStack {
                        ScrollView {
                            VStack(alignment: .leading, spacing: 28) {
                                content(summary, expanded: true)
                                VStack(alignment: .leading, spacing: 18) {
                                    Text(spanish ? "Tu balance" : "Your balance").font(CuadraoTypography.section)
                                    breakdown("loop.home.cash", minor: summary.cashMinor, summary: summary)
                                    if summary.otherAssetsMinor != "0" {
                                        breakdown("loop.home.other", minor: summary.otherAssetsMinor, summary: summary)
                                    }
                                    breakdown("loop.home.debt", minor: summary.debtsMinor, summary: summary)
                                }
                            }.padding(24)
                        }.background(WelcomePalette.background)
                            .navigationTitle("Balance").navigationBarTitleDisplayMode(.inline)
                            .toolbar {
                                ToolbarItem(placement: .confirmationAction) {
                                    Button(spanish ? "Listo" : "Done") { expanded = false }
                                        .accessibilityIdentifier("home.balance.close")
                                }
                            }
                    }.foregroundStyle(WelcomePalette.ink).tint(WelcomePalette.pine)
                }
        }
    }

    private func content(_ summary: FinancialCurrencySummary, expanded: Bool) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            CuadraoBalanceAmount(amount: summary.knownAccounts > 0 ? amount(summary.netWorthMinor, summary) : "—",
                currency: summary.currency, currencies: home.currencies.map(\.currency), spanish: spanish,
                expanded: expanded, amountIdentifier: "home.netWorth." + summary.currency,
                chooseCurrency: { chosenCurrency = $0 }, expand: { self.expanded = true })
            Text(summary.unknownAccounts > 0
                 ? (spanish ? "Balance parcial" : "Partial balance")
                 : (spanish ? "Balance neto" : "Net balance"))
                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                .accessibilityIdentifier("home-chart-date")
            if summary.unknownAccounts > 0 {
                Text(verbatim: String(format: NSLocalizedString("loop.home.unknownCount", comment: ""), summary.unknownAccounts))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            CuadraoChartState(title: spanish ? "Tu balance, a tu ritmo" : "Your balance, at your pace",
                detail: spanish ? "Puedes ver tu balance actual. El historial aún no está disponible."
                    : "You can see your current balance. History is not available yet.")
                .accessibilityIdentifier("home-chart-empty")
            if expanded, let asOf = summary.asOf {
                Text(AccountPresentation.date(asOf, zone: home.period?.timeZone ?? TimeZone.current.identifier, locale: locale))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
        }
    }

    private func breakdown(_ title: LocalizedStringKey, minor: String, summary: FinancialCurrencySummary) -> some View {
        HStack {
            Text(title).font(CuadraoTypography.body)
            Spacer(minLength: 12)
            Text(summary.knownAccounts > 0 ? amount(minor, summary) : "—").font(CuadraoTypography.rowAmount)
        }
    }

    private func amount(_ minor: String, _ summary: FinancialCurrencySummary) -> String {
        AccountPresentation.amount(AccountPresentation.decimal(minor, digits: summary.currencyFractionDigits), locale: locale)
    }
}
