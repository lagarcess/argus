import Foundation
import ArgusSession

struct ConnectedBalanceSummary {
    enum Component: String, CaseIterable {
        case cash, otherAssets
        var titleKey: String { self == .cash ? "loop.home.cash" : "loop.home.other" }
    }

    let summary: FinancialCurrencySummary
    var known: Bool { summary.knownAccounts > 0 }
    var components: [Component] {
        known ? Component.allCases.filter { minor($0) != "0" } : []
    }
    var deductions: String? { known && summary.debtsMinor != "0" ? summary.debtsMinor : nil }

    func minor(_ component: Component) -> String {
        component == .cash ? summary.cashMinor : summary.otherAssetsMinor
    }
    func amount(_ minor: String, locale: Locale) -> String {
        AccountPresentation.amount(AccountPresentation.decimal(minor, digits: summary.currencyFractionDigits), locale: locale)
    }
    func balance(locale: Locale) -> String? {
        known ? amount(summary.netWorthMinor, locale: locale) : nil
    }
    func fraction(_ component: Component) -> Double {
        guard known, let assets = Decimal(string: summary.assetsMinor), assets > 0,
              let value = Decimal(string: minor(component)) else { return 0 }
        return NSDecimalNumber(decimal: value / assets).doubleValue
    }
}
