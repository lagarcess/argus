import SwiftUI

struct CuadraoSampleAccount: Identifiable, Hashable {
    let id: String
    var name: String
    let kind: String
    let symbol: String
    let openingCents: Int
    var archived = false
}

struct CuadraoSampleExpense: Identifiable {
    let id = UUID()
    let accountID: String
    let title: String
    let category: String
    let cents: Int
}

/// Disposable interaction fixtures, never used by the financial client or API.
@Observable
final class CuadraoSampleData {
    var accounts = [
        CuadraoSampleAccount(id: "daily", name: "Día a día", kind: "Banco", symbol: "building.columns", openingCents: 4250000),
        CuadraoSampleAccount(id: "cash", name: "Efectivo", kind: "Efectivo", symbol: "banknote", openingCents: 320000),
        CuadraoSampleAccount(id: "safety", name: "Mi tranquilidad", kind: "Ahorros", symbol: "leaf", openingCents: 6800000)
    ]
    var expenses = [
        CuadraoSampleExpense(accountID: "daily", title: "Almuerzo", category: "Comida", cents: 65000),
        CuadraoSampleExpense(accountID: "daily", title: "Supermercado", category: "Compras", cents: 245000),
        CuadraoSampleExpense(accountID: "cash", title: "Café", category: "Comida", cents: 18000)
    ]

    var active: [CuadraoSampleAccount] { accounts.filter { !$0.archived } }
    func balance(_ account: CuadraoSampleAccount) -> Int {
        account.openingCents - expenses.filter { $0.accountID == account.id }.reduce(0) { $0 + $1.cents }
    }
    var total: Int { active.reduce(0) { $0 + balance($1) } }
}
