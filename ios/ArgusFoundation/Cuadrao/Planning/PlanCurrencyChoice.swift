import SwiftUI

struct PlanCurrencyChoice: View {
    @Binding var currency: String
    let locked: Bool
    let spanish: Bool
    var showLock = true
    var body: some View {
        if locked {
            chip(symbol: showLock ? "lock" : nil)
                .foregroundStyle(.secondary)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(spanish ? "Moneda fija: \(currency)" : "Fixed currency: \(currency)")
                .accessibilityIdentifier(showLock ? "plan-currency-fixed" : "plan-currency-inherited")
        } else {
            Menu {
                Picker(spanish ? "Moneda" : "Currency", selection: $currency) {
                    ForEach(PlanCurrency.supported, id: \.self) { Text($0).tag($0) }
                }
            } label: { chip(symbol: "chevron.down") }
                .buttonStyle(.plain).foregroundStyle(WelcomePalette.pine)
                .accessibilityLabel(spanish ? "Moneda, \(currency)" : "Currency, \(currency)")
                .accessibilityIdentifier("plan-edit-currency")
        }
    }
    private func chip(symbol: String?) -> some View {
        HStack(spacing: 6) {
            Text(currency).font(.subheadline.weight(.medium))
            if let symbol { Image(systemName: symbol).font(.caption2.weight(.semibold)) }
        }.fixedSize().padding(.horizontal, 12).frame(minHeight: 44)
            .background(WelcomePalette.ink.opacity(0.045), in: Capsule())
    }
}
