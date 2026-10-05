import Foundation

@main enum ConnectedBalanceSummaryChecks {
    static func main() {
        var checks = 0
        func check(_ condition: Bool, _ title: String) {
            precondition(condition, title)
            checks += 1
        }
        let locale = Locale(identifier: "en_US")
        var summary = FinancialCurrencySummary(currency: "DOP", currencyFractionDigits: 2,
            cashMinor: "150000", otherAssetsMinor: "50000", asOf: "2026-10-05T12:00:00Z",
            assetsMinor: "200000", debtsMinor: "250000", netWorthMinor: "-50000",
            knownAccounts: 3, unknownAccounts: 1, recordedSpendingMinor: "700")
        var value = ConnectedBalanceSummary(summary: summary)
        check(value.balance(locale: locale) == "-500.00", "Negative net balance keeps its sign")
        check(value.components == [.cash, .otherAssets], "Separate positive asset components")
        check(value.fraction(.cash) == 0.75 && value.fraction(.otherAssets) == 0.25,
            "Allocation uses positive assets, not net balance or debt")
        check(value.deductions == "250000", "Debt is the server's separate magnitude")
        check(value.minor(.cash) == summary.cashMinor, "Cash retains the server's owner-share projection")
        check(value.minor(.otherAssets) == summary.otherAssetsMinor, "Other assets retain the server projection")

        summary.cashMinor = "9223372036854775807"
        summary.otherAssetsMinor = summary.cashMinor
        summary.assetsMinor = "18446744073709551614"
        summary.netWorthMinor = "18446744073709551613"
        summary.debtsMinor = "1"
        value = ConnectedBalanceSummary(summary: summary)
        check(value.balance(locale: locale) == "184,467,440,737,095,516.13", "Aggregate beyond Int64 preserves every minor unit")
        check(value.amount(value.minor(.cash), locale: locale) == "92,233,720,368,547,758.07",
            "Account-scale amount does not round through Double")
        check(value.fraction(.cash) == 0.5, "Large exact values retain allocation proportions")
        check(value.amount(value.deductions!, locale: locale) == "0.01", "One minor unit remains visible")

        summary.cashMinor = "0"
        summary.otherAssetsMinor = "0"
        summary.assetsMinor = "0"
        summary.debtsMinor = "0"
        summary.netWorthMinor = "0"
        summary.knownAccounts = 1
        value = ConnectedBalanceSummary(summary: summary)
        check(value.balance(locale: locale) == "0.00", "Known zero remains visible even with an unknown account")
        check(value.components.isEmpty && value.deductions == nil, "Zero draws no positive share or deduction")
        check(value.fraction(.cash) == 0, "Zero assets do not divide by zero")

        summary.knownAccounts = 0
        value = ConnectedBalanceSummary(summary: summary)
        check(value.balance(locale: locale) == nil, "Unknown balance never becomes zero")
        check(value.components.isEmpty && value.deductions == nil, "Unknown balances create no allocation")

        for (currency, digits, expected) in [("JPY", 0, "1,001"), ("KWD", 3, "1.001")] {
            summary.currency = currency
            summary.currencyFractionDigits = digits
            summary.knownAccounts = 1
            summary.netWorthMinor = "1001"
            summary.cashMinor = summary.netWorthMinor
            summary.assetsMinor = summary.netWorthMinor
            value = ConnectedBalanceSummary(summary: summary)
            check(value.balance(locale: locale) == expected, "Currency precision comes from the same summary as its amount")
            check(value.summary.currency == currency, "Currency stays separate without conversion")
        }
        check(value.balance(locale: Locale(identifier: "es_ES")) == "1,001", "Localized separators preserve minor units")
        print("\(checks) connected balance summary checks passed")
    }
}
