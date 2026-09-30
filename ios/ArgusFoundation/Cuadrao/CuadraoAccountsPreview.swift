import SwiftUI

// Local design fixtures only. The financial client remains the owner of real money.
enum CanvasAccountKind: String, CaseIterable, Identifiable {
    case cash, checking, savings, investment, card, loan, property, vehicle, asset
    var id: String { rawValue }
    var isDebt: Bool { self == .card || self == .loan }
    var isAsset: Bool { [.property, .vehicle, .asset].contains(self) }
    func title(_ es: Bool) -> String {
        switch self {
        case .cash: es ? "Efectivo" : "Cash"
        case .checking: es ? "Cuenta corriente" : "Checking"
        case .savings: es ? "Ahorros" : "Savings"
        case .investment: es ? "Inversión" : "Investment"
        case .card: es ? "Tarjeta de crédito" : "Credit card"
        case .loan: es ? "Préstamo" : "Loan"
        case .property: es ? "Propiedad" : "Property"
        case .vehicle: es ? "Vehículo" : "Vehicle"
        case .asset: es ? "Otro activo" : "Other asset"
        }
    }
}

struct CanvasAccount: Identifiable {
    var id = UUID()
    var name: String
    var kind: CanvasAccountKind
    var currency = "DOP"
    var balance: Decimal?
    var share = 100
    var archived = false
    func displayName(_ es: Bool) -> String { name.isEmpty ? kind.title(es) : name }
    func balanceLabel(_ es: Bool) -> String {
        kind.isDebt ? (es ? "Monto pendiente" : "Amount owed") : kind.isAsset
            ? (es ? "Valor estimado" : "Estimated value") : (es ? "Balance" : "Balance")
    }
}

struct CanvasActivity: Identifiable {
    var id = UUID()
    let accountID: UUID
    let title: String
    let amount: Decimal
    let date: Date
    let income: Bool
}

@Observable final class CuadraoAccountsPreview {
    var accounts: [CanvasAccount] = []
    var activity: [CanvasActivity] = []
    init(populated: Bool, spanish: Bool) { reset(populated: populated, spanish: spanish) }
    var active: [CanvasAccount] { accounts.filter { !$0.archived } }
    var archived: [CanvasAccount] { accounts.filter(\.archived) }
    func account(_ id: UUID) -> CanvasAccount? { accounts.first { $0.id == id } }
    func replace(_ account: CanvasAccount) {
        if let i = accounts.firstIndex(where: { $0.id == account.id }) { accounts[i] = account }
        else { accounts.append(account) }
    }
    func archive(_ id: UUID, _ archived: Bool) {
        guard let i = accounts.firstIndex(where: { $0.id == id }) else { return }
        accounts[i].archived = archived
    }
    func move(from: IndexSet, to: Int) {
        var visible = active
        visible.move(fromOffsets: from, toOffset: to)
        accounts = visible + archived
    }
    func reset(populated: Bool, spanish: Bool) {
        accounts = populated ? [
            CanvasAccount(name: spanish ? "Día a día" : "Everyday", kind: .checking, balance: 39400),
            CanvasAccount(name: "", kind: .cash, balance: 3020),
            CanvasAccount(name: spanish ? "Mi tranquilidad" : "Peace of mind", kind: .savings, balance: 68000)
        ] : []
        activity = []
        if let first = accounts.first, let cash = accounts.last(where: { $0.kind == .cash }) {
            activity = [
                CanvasActivity(accountID: first.id, title: spanish ? "Almuerzo" : "Lunch", amount: 650, date: .now, income: false),
                CanvasActivity(accountID: cash.id, title: spanish ? "Café" : "Coffee", amount: 180, date: .now, income: false)
            ]
        }
    }
}

/// Formatting only; the preview does not connect to the financial ledger.
enum CanvasMoney {
    static let maximum = Decimal(string: "9999999.99")!
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

struct CanvasAccountIcon: View {
    let kind: CanvasAccountKind
    var size: CGFloat = 23
    var body: some View {
        Image("CuadraoAccount-" + kind.rawValue)
            .resizable().scaledToFit().frame(width: size, height: size)
            .foregroundStyle(WelcomePalette.pine).accessibilityHidden(true)
    }
}

struct CanvasActionRow: View {
    let title: String
    let symbol: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                Image(systemName: symbol).frame(width: 24).accessibilityHidden(true)
                Text(title).frame(maxWidth: .infinity, alignment: .leading)
            }.font(.body).padding(.vertical, 17).contentShape(Rectangle())
        }.buttonStyle(.plain)
    }
}

struct CanvasAccountRow: View {
    let account: CanvasAccount
    let spanish: Bool
    var body: some View {
        HStack(spacing: 12) {
            CanvasAccountIcon(kind: account.kind)
                .frame(width: 42, height: 42)
                .background(WelcomePalette.sage.opacity(0.65), in: RoundedRectangle(cornerRadius: 13))
            VStack(alignment: .leading, spacing: 5) {
                Text(account.displayName(spanish)).font(.body.weight(.medium))
                Text(account.kind.title(spanish)).font(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 5) {
                Text(account.balance.map { CanvasMoney.format($0, currency: account.currency) } ?? "—")
                    .font(.subheadline.weight(.medium)).monospacedDigit()
                Text(account.currency + (account.kind.isDebt ? (spanish ? " · pendiente" : " · owed") : ""))
                    .font(.caption).foregroundStyle(.secondary)
            }
        }.padding(.vertical, 12).contentShape(Rectangle())
    }
}
