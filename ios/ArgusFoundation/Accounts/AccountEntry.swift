import Foundation

/// Text-only locale conversion. Currency precision and validity remain server-owned.
enum AccountEntry {
    enum Failure: Error { case amount, share }
    static func amount(_ raw: String, locale: Locale) throws -> String? {
        if raw.isEmpty { return nil }
        let decimal = locale.decimalSeparator ?? "."
        let grouping = locale.groupingSeparator ?? ","
        let d = NSRegularExpression.escapedPattern(for: decimal)
        let g = NSRegularExpression.escapedPattern(for: grouping)
        let pattern = "^-?(?:[0-9]+|[0-9]{1,3}(?:" + g + "[0-9]{3})+)(?:" + d + "[0-9]+)?$"
        guard raw.range(of: pattern, options: .regularExpression) != nil else { throw Failure.amount }
        return raw.replacingOccurrences(of: grouping, with: "").replacingOccurrences(of: decimal, with: ".")
    }
    static func share(_ raw: String) throws -> Int {
        guard raw.range(of: "^[0-9]{1,3}(?:[.][0-9]{1,2})?$", options: .regularExpression) != nil else { throw Failure.share }
        let parts = raw.split(separator: ".")
        guard let whole = Int(parts[0]) else { throw Failure.share }
        let fraction = parts.count > 1 ? String(parts[1]) : ""
        let bps = whole * 100 + (Int(fraction.padding(toLength: 2, withPad: "0", startingAt: 0)) ?? 0)
        guard (1...10000).contains(bps) else { throw Failure.share }
        return bps
    }
}
