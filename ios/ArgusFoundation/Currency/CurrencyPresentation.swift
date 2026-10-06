import Foundation

enum CurrencyPresentation {
    static func selectedCode(available: [String], explicit: String?, primary: String?) -> String? {
        if let explicit, available.contains(explicit) { return explicit }
        if let primary, available.contains(primary) { return primary }
        return available.count == 1 ? available.first : nil
    }

    static func ordered<Value>(_ values: [Value], primary: String?, currency: (Value) -> String) -> [Value] {
        values.sorted { left, right in
            let leftCode = currency(left)
            let rightCode = currency(right)
            if leftCode == rightCode { return false }
            if leftCode == primary { return true }
            if rightCode == primary { return false }
            return leftCode < rightCode
        }
    }
}
