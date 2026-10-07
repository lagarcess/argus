import SwiftUI

struct ConnectedProfileCurrencyRow: View {
    @ObservedObject var model: ProfileAuthModel
    let spanish: Bool
    private var title: String { spanish ? "Moneda preferida" : "Preferred currency" }
    private var value: String { model.profile?.currency ?? (spanish ? "Elegir" : "Choose") }

    var body: some View {
        HStack {
            Text(title)
            Spacer()
            CuadraoChoiceMenu(title: title,
                selection: Binding(
                    get: { value },
                    set: { value in Task { await model.setPrimaryCurrency(value) } }),
                values: PlanCurrency.supported, valueTitle: { $0 })
                .buttonStyle(.borderless)
                .disabled(model.busy)
                .accessibilityLabel(title)
                .accessibilityValue(value)
                .accessibilityIdentifier("profile.primaryCurrency")
        }
        .accessibilityElement(children: .contain)
        if let key = model.errorKey {
            Text(LocalizedStringKey(key)).foregroundStyle(.red)
                .accessibilityIdentifier("profile.primaryCurrency.error")
        }
    }
}
