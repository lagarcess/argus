import Foundation

enum CurrencyPresentation {
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
