import SwiftUI

struct CuadraoHomeInsights: View {
    let accounts: [CanvasAccount]
    let observations: [CanvasBalanceObservation]
    let currency: String
    let spanish: Bool
    let space: String
    let shared: Bool
    @State private var distribution = false
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    Picker(spanish ? "Vista" : "View", selection: $distribution) {
                        Text(spanish ? "Evolución" : "History").tag(false)
                        Text(spanish ? "Distribución" : "Breakdown").tag(true)
                    }.pickerStyle(.segmented).accessibilityIdentifier("home-chart-view")
                    if distribution {
                        CuadraoHomeDistribution(accounts: accounts, currency: currency, spanish: spanish)
                    } else {
                        CuadraoHomeBalanceChart(accounts: accounts, observations: observations, currency: currency,
                            currencies: [currency], spanish: spanish, shared: shared, chooseCurrency: { _ in }, expanded: true)
                    }
                }.padding(.horizontal, 24).padding(.top, 16).padding(.bottom, 32)
            }.accessibilityIdentifier("home-insights-content").background(WelcomePalette.background)
                .navigationTitle(space).navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button { dismiss() } label: { Image(systemName: "xmark").frame(width: 44, height: 44) }
                            .accessibilityLabel(spanish ? "Cerrar" : "Close").accessibilityIdentifier("home-history-done")
                    }
                }
        }.tint(WelcomePalette.pine).foregroundStyle(WelcomePalette.ink)
    }
}
