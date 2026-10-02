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
    var spaceID = CanvasSpace.personalID
    var sharedWithHousehold = false
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
    var category: CanvasExpenseCategory = .other
}

@Observable final class CuadraoAccountsPreview {
    var accounts: [CanvasAccount] = []
    var activity: [CanvasActivity] = []
    var balanceObservations: [CanvasBalanceObservation] = []
    var expenseCoverageStarts: [UUID: Date] = [:]
    func spendingCoverageStart(currency: String) -> Date? {
        let ids = scopedAccounts.filter { $0.currency == currency }.map(\.id)
        let starts = ids.compactMap { expenseCoverageStarts[$0] }
        guard !ids.isEmpty, starts.count == ids.count else { return nil }
        return starts.max()
    }
    var spaces: [CanvasSpace] = []
    var household: CanvasHouseholdState = .alone
    var selectedSpaceID = CanvasSpace.personalID
    init(populated: Bool, spanish: Bool) { reset(populated: populated, spanish: spanish) }
    var active: [CanvasAccount] { scopedAccounts.filter { !$0.archived } }
    var archived: [CanvasAccount] { scopedAccounts.filter(\.archived) }
    func account(_ id: UUID) -> CanvasAccount? { accounts.first { $0.id == id } }
    func replace(_ account: CanvasAccount) {
        if let i = accounts.firstIndex(where: { $0.id == account.id }) { accounts[i] = account }
        else { accounts.append(account) }
    }
    func archive(_ id: UUID, _ archived: Bool) {
        guard let i = accounts.firstIndex(where: { $0.id == id }) else { return }
        accounts[i].archived = archived
    }
    func reorder(_ ids: [UUID]) {
        guard Set(ids) == Set(active.map(\.id)) else { return }
        accounts = CuadraoCollectionOrder.applying(ids, to: accounts)
        UserDefaults.standard.set(accounts.map { $0.id.uuidString }, forKey: "cuadrao.design.account-order")
    }
    func move(from: IndexSet, to: Int) {
        var visible = active
        visible.move(fromOffsets: from, toOffset: to)
        reorder(visible.map(\.id))
    }
    func reset(populated: Bool, spanish: Bool) {
        household = populated ? .joined("Alex") : .alone
        selectedSpaceID = CanvasSpace.personalID
        spaces = [CanvasSpace(id: CanvasSpace.personalID, kind: .personal, name: "")]
        if populated { spaces.append(CanvasSpace(id: CanvasSpace.householdID, kind: .household, name: "")) }
        accounts = populated ? [
            CanvasAccount(name: spanish ? "Día a día" : "Everyday", kind: .checking, balance: 39400),
            CanvasAccount(name: "", kind: .cash, balance: 3020),
            CanvasAccount(name: spanish ? "Mi tranquilidad" : "Peace of mind", kind: .savings, balance: 68000)
        ] : []
        if populated {
            accounts.append(CanvasAccount(name: spanish ? "Gastos de casa" : "Household spending",
                kind: .checking, balance: 18500, spaceID: CanvasSpace.householdID, sharedWithHousehold: true))
            accounts.append(CanvasAccount(name: spanish ? "Fondo de la casa" : "Household fund",
                kind: .savings, balance: 25000, spaceID: CanvasSpace.householdID, sharedWithHousehold: true))
        }
        // Stable local fixture identities allow a viewer's order to survive relaunch.
        for index in accounts.indices {
            accounts[index].id = UUID(uuidString: String(format: "00000000-0000-4000-8000-%012d", index + 1))!
        }
        let orderKey = "cuadrao.design.account-order"
        if ProcessInfo.processInfo.arguments.contains("--plan-reset") { UserDefaults.standard.removeObject(forKey: orderKey) }
        let saved = (UserDefaults.standard.stringArray(forKey: orderKey) ?? []).compactMap(UUID.init(uuidString:))
        let known = Set(accounts.map(\.id))
        let order = saved.filter { known.contains($0) } + accounts.map(\.id).filter { !saved.contains($0) }
        balanceObservations = populated ? CanvasBalanceHistory.examples(accounts: accounts, now: .now) : []
        activity = []
        expenseCoverageStarts = [:]
        if let first = accounts.first, let cash = accounts.last(where: { $0.kind == .cash }) {
            activity = [
                CanvasActivity(accountID: first.id, title: spanish ? "Almuerzo" : "Lunch", amount: 650, date: .now, income: false, category: .food),
                CanvasActivity(accountID: cash.id, title: spanish ? "Café" : "Coffee", amount: 180, date: .now, income: false, category: .food)
            ]
        }
        if let shared = accounts.first(where: { $0.sharedWithHousehold }) {
            activity.append(CanvasActivity(accountID: shared.id, title: spanish ? "Supermercado" : "Groceries",
                amount: 2450, date: .now, income: false, category: .groceries))
        }
        if populated {
            activity += CanvasSpendingHistory.examples(accounts: accounts, spanish: spanish, now: .now)
            // This preview explicitly owns a continuous recording window, including quiet days.
            let start = CanvasPreviewHistory.days(now: .now).first ?? .now
            expenseCoverageStarts = Dictionary(uniqueKeysWithValues: accounts.map { ($0.id, start) })
            if ProcessInfo.processInfo.arguments.contains("--insights-empty-month") {
                let month = Calendar.current.dateInterval(of: .month, for: Date.now)!
                activity.removeAll { $0.date >= month.start }
            }
            if ProcessInfo.processInfo.arguments.contains("--insights-first-use") {
                activity = []; expenseCoverageStarts = [:]; balanceObservations = []
            }
            if ProcessInfo.processInfo.arguments.contains("--insights-no-coverage") { expenseCoverageStarts = [:] }
            accounts = CuadraoCollectionOrder.applying(order, to: accounts)
        }
    }
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
                Text(account.kind.title(spanish) + (account.sharedWithHousehold ? (spanish ? " · Conjunta" : " · Joint") : ""))
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 5) {
                Text(account.balance.map { CanvasMoney.format($0, currency: account.currency) } ?? "—")
                    .font(CuadraoTypography.rowAmount)
                Text(account.currency + (account.kind.isDebt ? (spanish ? " · pendiente" : " · owed") : ""))
                    .font(.caption).foregroundStyle(.secondary)
            }
        }.padding(.vertical, 12).contentShape(Rectangle())
    }
}
