import SwiftUI

struct PlanCurrencyChoice: View {
    @Binding var currency: String
    let locked: Bool
    let spanish: Bool
    var showLock = true
    var body: some View {
        if locked {
            CuadraoChoiceLabel(title: currency, selectable: false, locked: showLock)
                .foregroundStyle(.secondary)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(spanish ? "Moneda fija: \(currency)" : "Fixed currency: \(currency)")
                .accessibilityIdentifier(showLock ? "plan-currency-fixed" : "plan-currency-inherited")
        } else {
            CuadraoChoiceMenu(title: spanish ? "Moneda" : "Currency", selection: $currency,
                values: PlanCurrency.supported, valueTitle: { $0 })
                .buttonStyle(.plain).foregroundStyle(WelcomePalette.pine)
                .accessibilityLabel(spanish ? "Moneda, \(currency)" : "Currency, \(currency)")
                .accessibilityIdentifier("plan-edit-currency")
        }
    }
}
