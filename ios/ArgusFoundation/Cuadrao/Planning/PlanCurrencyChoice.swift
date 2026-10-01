import SwiftUI

struct PlanCurrencyChoice: View {
    @Binding var currency: String
    let locked: Bool
    let spanish: Bool
    var body: some View {
        if locked {
            Label(currency, systemImage: "lock").font(.subheadline).foregroundStyle(.secondary)
                .accessibilityLabel(spanish ? "Moneda fija: \(currency)" : "Fixed currency: \(currency)")
                .accessibilityIdentifier("plan-currency-fixed")
        } else {
            Picker(spanish ? "Moneda" : "Currency", selection: $currency) {
                ForEach(PlanCurrency.supported, id: \.self) { Text($0).tag($0) }
            }.pickerStyle(.menu).accessibilityIdentifier("plan-edit-currency")
        }
    }
}
