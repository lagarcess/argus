import SwiftUI

struct ConnectedProfileCurrencyRow: View {
    @ObservedObject var model: ProfileAuthModel
    let spanish: Bool

    var body: some View {
        LabeledContent(spanish ? "Moneda preferida" : "Preferred currency") {
            CuadraoChoiceMenu(title: spanish ? "Moneda preferida" : "Preferred currency",
                selection: Binding(
                    get: { model.profile?.currency ?? (spanish ? "Elegir" : "Choose") },
                    set: { value in Task { await model.setPrimaryCurrency(value) } }),
                values: PlanCurrency.supported, valueTitle: { $0 })
                .disabled(model.busy)
                .accessibilityIdentifier("profile.primaryCurrency")
        }
        .accessibilityElement(children: .contain)
        if let key = model.errorKey {
            Text(LocalizedStringKey(key)).foregroundStyle(.red)
                .accessibilityIdentifier("profile.primaryCurrency.error")
        }
    }
}
