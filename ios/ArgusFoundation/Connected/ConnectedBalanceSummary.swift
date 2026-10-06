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

/// The server's own monthly period is the only canonical activity read. Its coverage is
/// `recorded_only`, so a zero is never a proven zero and every other page has no data.
enum ConnectedSpendingPeriod: Equatable {
    case recorded(minor: String)
    case noData

    static func reading(summary: FinancialCurrencySummary, period: FinancialHomePeriod?, page: DateInterval,
                        calendar: Calendar = .current) -> Self {
        guard let period, let start = AccountPresentation.parseDate(period.startAt),
              let end = AccountPresentation.parseDate(period.endAtExclusive),
              start == page.start, end == page.end,
              let minor = summary.grossPurchasesMinor, let value = Decimal(string: minor), value > 0 else { return .noData }
        return .recorded(minor: minor)
    }
}
