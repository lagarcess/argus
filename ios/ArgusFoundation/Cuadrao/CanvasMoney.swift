import Foundation

/// Formatting only; the preview does not connect to the financial ledger.
enum CanvasMoney {
    static let maximum = Decimal(string: "9999999.99")!
    static var maximumValue: Double { NSDecimalNumber(decimal: maximum).doubleValue }
    static var maximumCents: Int { NSDecimalNumber(decimal: maximum * 100).intValue }
    static func digits(_ currency: String) -> Int {
        let formatter = NumberFormatter(); formatter.numberStyle = .currency
        formatter.currencyCode = currency
        return formatter.maximumFractionDigits
    }
    static func format(_ value: Decimal, currency: String) -> String {
        let formatter = NumberFormatter(); formatter.locale = Locale(identifier: "en_US")
        formatter.numberStyle = .decimal
        formatter.minimumFractionDigits = digits(currency)
        formatter.maximumFractionDigits = digits(currency)
        return formatter.string(from: NSDecimalNumber(decimal: value)) ?? "—"
    }
    static func raw(_ value: Decimal) -> String { NSDecimalNumber(decimal: value).stringValue }
}

