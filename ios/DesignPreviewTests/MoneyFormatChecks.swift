import Foundation

/// The formatter-per-call implementation `CanvasMoney` shipped before it reused formatters.
private enum LegacyMoney {
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
}

@main enum MoneyFormatChecks {
    static func main() {
        var checks = 0
        func check(_ condition: Bool, _ title: String) {
            precondition(condition, title); checks += 1
        }
        let values = ["0", "-0", "0.004", "0.005", "0.015", "0.025", "-0.005", "0.5", "1", "-1", "9.99", "10", "999", "999.995",
            "1000", "-1000", "1234.5", "1234.5678", "-1234.5678", "12345.678901", "100000", "999999.99", "1000000",
            "1234567.891", "9999999.99", "-9999999.99", "10000000", "123456789012345.67", "0.0001", "0.00049", "0.0005",
            "2.675", "1e-7", "7e12"].map { Decimal(string: $0)! }
        let currencies = Locale.commonISOCurrencyCodes
            + ["USD", "DOP", "EUR", "JPY", "KWD", "BHD", "CLF", "UYW", "usd", "dop", "", " ", "XXX", "ZZZ", "US", "DOLLAR", "€"]
        var compared = 0
        for currency in currencies {
            check(CanvasMoney.digits(currency) == LegacyMoney.digits(currency), "Fraction digits match for \(currency)")
            for value in values {
                let expected = LegacyMoney.format(value, currency: currency)
                let actual = CanvasMoney.format(value, currency: currency)
                check(Array(actual.utf8) == Array(expected.utf8), "\(currency) \(value): \(actual) is not \(expected)")
                compared += 1
            }
        }
        // Repeats read the reused formatter; a second sweep proves it kept no state from the first.
        for currency in currencies.reversed() {
            for value in values.reversed() {
                check(CanvasMoney.format(value, currency: currency) == LegacyMoney.format(value, currency: currency),
                    "Repeat \(currency) \(value)")
            }
        }
        let literal: [(String, String, String)] = [
            ("1234567.891", "USD", "1,234,567.89"), ("1234567.891", "DOP", "1,234,567.89"), ("1234567.891", "JPY", "1,234,568"),
            ("1234567.8915", "KWD", "1,234,567.892"), ("0", "USD", "0.00"), ("0", "JPY", "0"), ("-1234.5", "EUR", "-1,234.50"),
            ("0.005", "USD", "0.00"), ("0.015", "USD", "0.02"), ("0.025", "USD", "0.02"), ("9999999.99", "DOP", "9,999,999.99"),
        ]
        for (value, currency, expected) in literal {
            check(CanvasMoney.format(Decimal(string: value)!, currency: currency) == expected, "\(currency) \(value) reads \(expected)")
        }
        check(CanvasMoney.digits("USD") == 2 && CanvasMoney.digits("JPY") == 0 && CanvasMoney.digits("KWD") == 3, "Known fraction digits")

        let threaded = currencies.prefix(24).flatMap { currency in values.map { (currency, $0) } }
        let expected = threaded.map { LegacyMoney.format($0.1, currency: $0.0) }
        let failures = Failures()
        DispatchQueue.concurrentPerform(iterations: 16) { worker in
            for round in 0..<40 {
                let index = (worker * 7919 + round * 31) % threaded.count
                for offset in 0..<threaded.count {
                    let at = (index + offset) % threaded.count
                    if CanvasMoney.format(threaded[at].1, currency: threaded[at].0) != expected[at] { failures.add() }
                }
            }
        }
        check(failures.count == 0, "Concurrent callers read the same strings")

        let sample = Decimal(string: "1234567.89")!
        func time(_ body: () -> Void) -> Double {
            let start = DispatchTime.now().uptimeNanoseconds; body()
            return Double(DispatchTime.now().uptimeNanoseconds - start) / 2000 / 1000
        }
        let legacy = time { for _ in 0..<2000 { _ = LegacyMoney.format(sample, currency: "DOP") } }
        let current = time { for _ in 0..<2000 { _ = CanvasMoney.format(sample, currency: "DOP") } }
        print("locale \(Locale.current.identifier): \(compared) value and currency pairs byte-identical; "
            + String(format: "per call %.1f µs before, %.1f µs now", legacy, current))
        print("Passed \(checks) money format checks")
    }
}

private final class Failures: @unchecked Sendable {
    private let lock = NSLock()
    private(set) var count = 0
    func add() { lock.lock(); count += 1; lock.unlock() }
}
