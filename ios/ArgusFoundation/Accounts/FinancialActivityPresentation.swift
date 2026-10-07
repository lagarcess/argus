import Foundation

enum FinancialActivityPresentation {
    static func sign(for movement: Int64) -> String { movement > 0 ? "+" : movement < 0 ? "−" : "" }

    static func signedAmount(_ movement: Int64, digits: Int, locale: Locale) -> String {
        let exact = AccountPresentation.decimal(movement, digits: digits)
        let magnitude = movement < 0 ? String(exact.dropFirst()) : exact
        return sign(for: movement) + AccountPresentation.amount(magnitude, locale: locale)
    }

    static func symbol(for kind: String) -> String {
        switch kind {
        case "expense": "arrow.up.right"
        case "income": "arrow.down.left"
        case "transfer": "arrow.left.arrow.right"
        case "card_payment", "debt_payment": "creditcard"
        case "payment_reversal", "refund": "arrow.uturn.backward"
        default: "doc.text"
        }
    }
}
