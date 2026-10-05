import SwiftUI
import ArgusSession

struct ConnectedAccountRow: View {
    let account: FinancialAccount
    let spanish: Bool
    @Environment(\.locale) private var locale

    var body: some View {
        CanvasAccountRowContent(value: ConnectedAccountPresentation.row(account, spanish: spanish, locale: locale))
    }
}

@MainActor
enum ConnectedAccountPresentation {
    static func artwork(_ type: String) -> CanvasAccountKind? {
        switch type {
        case "cash": .cash
        case "checking": .checking
        case "savings": .savings
        case "investment": .investment
        case "credit_card": .card
        case "other_debt": .loan
        case "property": .property
        case "vehicle": .vehicle
        case "other_asset": .asset
        default: nil
        }
    }

    static func title(_ account: FinancialAccount, spanish: Bool) -> String {
        account.nickname ?? artwork(account.type)?.title(spanish) ?? (spanish ? "Cuenta" : "Account")
    }

    static func row(_ account: FinancialAccount, spanish: Bool, locale: Locale) -> CanvasAccountRowValue {
        var notes: [String] = []
        if account.isOptionalAsset { notes.append(NSLocalizedString("assets.whole", comment: "")) }
        if account.ownershipShareBps != 10000 { notes.append(share(account, spanish: spanish, locale: locale)) }
        if account.archived { notes.append(spanish ? "Archivada" : "Archived") }
        let qualifier: String
        if account.balance.state == .known, account.type == "credit_card", (account.balance.creditMinor ?? 0) > 0 {
            qualifier = spanish ? " · a favor" : " · credit"
        } else if account.balance.state == .known, (account.balance.amountMinor ?? 0) < 0 {
            qualifier = spanish ? " · pendiente" : " · owed"
        } else { qualifier = "" }
        return CanvasAccountRowValue(
            title: title(account, spanish: spanish),
            subtitle: artwork(account.type)?.title(spanish) ?? account.type,
            artwork: artwork(account.type), amount: amount(account, spanish: spanish, locale: locale),
            amountCaption: account.currency + qualifier, note: notes.isEmpty ? nil : notes.joined(separator: " · "))
    }

    static func detail(_ account: FinancialAccount, spanish: Bool, locale: Locale) -> CanvasAccountDetailValue {
        let known = account.balance.state == .known
        let formatted = amount(account, spanish: spanish, locale: locale)
        let freshness: String
        if known, let asOf = account.balance.asOf {
            freshness = (spanish ? "Al " : "As of ") + AccountPresentation.date(asOf, zone: TimeZone.current.identifier, locale: locale)
        } else if known {
            freshness = spanish ? "Fecha de balance no disponible" : "Balance date unavailable"
        } else {
            freshness = spanish ? "Sin balance registrado" : "No balance recorded"
        }
        var notes = [share(account, spanish: spanish, locale: locale)]
        if known, account.type == "credit_card", (account.balance.creditMinor ?? 0) > 0 {
            notes.append(spanish ? "Saldo a tu favor" : "Credit balance in your favor")
        } else if account.nature == "liability" {
            notes.append(spanish ? "Saldo con signo: un monto negativo indica dinero que debes."
                : "Signed balance: a negative amount means money owed.")
        }
        if account.archived { notes.append(spanish ? "Archivada. Se conservan el balance y el historial." : "Archived. Balance and history are kept.") }
        return CanvasAccountDetailValue(title: title(account, spanish: spanish), artwork: artwork(account.type),
            balanceLabel: "Balance", currency: account.currency, amount: formatted,
            freshness: freshness, notes: notes, amountIdentifier: "accounts.balance." + account.currency,
            amountAccessibilityLabel: account.currency + " " + formatted)
    }

    private static func amount(_ account: FinancialAccount, spanish: Bool, locale: Locale) -> String {
        guard account.balance.state == .known, let amount = account.balance.amount else {
            return spanish ? "Saldo desconocido" : "Balance unknown"
        }
        return AccountPresentation.amount(amount, locale: locale)
    }

    private static func share(_ account: FinancialAccount, spanish: Bool, locale: Locale) -> String {
        (spanish ? "Tu parte: " : "Your share: ")
            + AccountPresentation.amount(AssetShareControl.percent(account.ownershipShareBps), locale: locale) + "%"
    }
}
