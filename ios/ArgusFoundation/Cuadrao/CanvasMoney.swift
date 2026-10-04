import Foundation

/// Formatting only; the preview does not connect to the financial ledger.
enum CanvasMoney {
    static let maximum = Decimal(string: "9999999.99")!
    static var maximumValue: Double { NSDecimalNumber(decimal: maximum).doubleValue }
    static var maximumCents: Int { NSDecimalNumber(decimal: maximum * 100).intValue }
    static func digits(_ currency: String) -> Int { formatters.digits(currency) }
    static func format(_ value: Decimal, currency: String) -> String {
        formatters.string(value, digits: digits(currency))
    }
    static func raw(_ value: Decimal) -> String { NSDecimalNumber(decimal: value).stringValue }
}

/// A formatter is built once per configuration; the fraction digits follow the device locale, so it keys them.
private let formatters = CanvasMoneyFormatters()
private final class CanvasMoneyFormatters: @unchecked Sendable {
    private struct Currency: Hashable { let locale: String, code: String }
    private let lock = NSLock()
    private var digits: [Currency: Int] = [:]
    private var decimal: [Int: NumberFormatter] = [:]
    func digits(_ currency: String) -> Int {
        let key = Currency(locale: Locale.current.identifier, code: currency)
        lock.lock(); defer { lock.unlock() }
        if let known = digits[key] { return known }
        let formatter = NumberFormatter(); formatter.numberStyle = .currency
        formatter.currencyCode = currency
        digits[key] = formatter.maximumFractionDigits
        return formatter.maximumFractionDigits
    }
    func string(_ value: Decimal, digits: Int) -> String {
        lock.lock(); defer { lock.unlock() }
        let formatter = decimal[digits] ?? {
            let formatter = NumberFormatter(); formatter.locale = Locale(identifier: "en_US")
            formatter.numberStyle = .decimal
            formatter.minimumFractionDigits = digits
            formatter.maximumFractionDigits = digits
            decimal[digits] = formatter
            return formatter
        }()
        return formatter.string(from: NSDecimalNumber(decimal: value)) ?? "—"
    }
}
