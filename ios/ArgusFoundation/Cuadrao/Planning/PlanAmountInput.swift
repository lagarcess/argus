import SwiftUI

/// Plan composition around the same editing behavior as Accounts.
struct PlanAmountInput: View {
    @Binding var value: Double
    @Binding var currency: String
    @Binding var error: String
    let title: String
    let identifier: String
    let spanish: Bool
    var currencySelectable = false
    var showCurrencyLock = false
    var prominent = true
    @State private var focused = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .center, spacing: 12) {
                PlanCurrencyChoice(currency: $currency, locked: !currencySelectable,
                                   spanish: spanish, showLock: showCurrencyLock)
                CanvasMoneyValueInput(value: $value, error: $error, currency: currency, spanish: spanish,
                                      identifier: identifier, title: title, size: prominent ? .prominent : .secondary,
                                      onFocus: { focused = $0 })
                    .frame(minWidth: 0, maxWidth: .infinity, minHeight: 52)
                    .overlay(alignment: .bottom) {
                        Rectangle().fill(!error.isEmpty ? .red : focused ? WelcomePalette.pine : WelcomePalette.ink.opacity(0.12))
                            .frame(height: focused ? 2 : 1)
                    }
            }
            if !error.isEmpty {
                Text(error).font(CuadraoTypography.caption).foregroundStyle(.red)
                    .accessibilityIdentifier(identifier + "-error")
            }
        }
    }
}
