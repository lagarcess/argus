import SwiftUI

struct CuadraoHomeInsights: View {
    let data: CuadraoAccountsPreview
    private var accounts: [CanvasAccount] { data.active.filter { $0.currency == currency } }
    let currency: String
    let spanish: Bool
    let space: String
    let shared: Bool
    @State private var distribution = false
    @State private var accountPath: [UUID] = []
    @State private var accountSheet: CanvasAccountSheet?
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack(path: $accountPath) {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    Picker(spanish ? "Vista" : "View", selection: $distribution) {
                        Text(spanish ? "Evolución" : "History").tag(false)
                        Text(spanish ? "Distribución" : "Breakdown").tag(true)
                    }.pickerStyle(.segmented).accessibilityIdentifier("home-chart-view")
                    if distribution {
                        CuadraoHomeDistribution(accounts: accounts, currency: currency, spanish: spanish)
                    } else {
                        CuadraoHomeBalanceChart(accounts: accounts, observations: data.balanceObservations, currency: currency,
                            currencies: [currency], spanish: spanish, shared: shared, chooseCurrency: { _ in }, expanded: true)
                    }
                }.padding(.horizontal, 24).padding(.top, 16).padding(.bottom, 32)
            }.accessibilityIdentifier("home-insights-content").background(WelcomePalette.background)
                .navigationDestination(for: UUID.self) { id in
                    CuadraoAccountCanvas(data: data, accountID: id, spanish: spanish,
                        actions: { accountSheet = .actions($0) }, record: { accountSheet = .record($0) })
                }
                .navigationTitle(space).navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button { dismiss() } label: { Image(systemName: "xmark").frame(width: 44, height: 44) }
                            .accessibilityLabel(spanish ? "Cerrar" : "Close").accessibilityIdentifier("home-history-done")
                    }
                }
        }.sheet(item: $accountSheet) { selection in
            CuadraoAccountModal(data: data, selection: selection, spanish: spanish,
                show: { accountSheet = $0 }, archived: { _ in
                    accountSheet = nil; accountPath = []
                })
        }.tint(WelcomePalette.pine).foregroundStyle(WelcomePalette.ink)
    }
}
