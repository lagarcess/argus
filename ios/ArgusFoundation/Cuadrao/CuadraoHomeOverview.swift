import SwiftUI

struct CuadraoHomeOverview: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    @State private var chosenCurrency: String?
    @State private var expanded = false
    private var currencies: [String] { Set(data.active.map(\.currency)).sorted() }
    private var currency: String { chosenCurrency.flatMap { currencies.contains($0) ? $0 : nil } ?? currencies.first ?? "DOP" }
    var body: some View {
        CuadraoHomeBalanceChart(accounts: data.active.filter { $0.currency == currency },
            observations: data.balanceObservations, currency: currency, currencies: currencies,
            spanish: spanish, shared: data.selectedSpace.kind == .household,
            chooseCurrency: { chosenCurrency = $0 }, expand: { expanded = true })
            .id(data.selectedSpaceID + currency)
            .fullScreenCover(isPresented: $expanded) {
                CuadraoHomeInsights(data: data, currency: currency, spanish: spanish,
                    space: data.selectedSpace.title(spanish), shared: data.selectedSpace.kind == .household)
            }
    }
}
