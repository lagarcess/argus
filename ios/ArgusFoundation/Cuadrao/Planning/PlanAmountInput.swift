import SwiftUI

/// One amount treatment for plan targets, shared expenses and repayments.
struct PlanAmountInput: View {
    @Binding var value: Double
    @Binding var currency: String
    let title: String
    let identifier: String
    let spanish: Bool
    var currencySelectable = false
    var showCurrencyLock = false
    var prominent = true
    @FocusState private var focused: Bool
    @ScaledMetric(relativeTo: .largeTitle) private var largeSize = 36
    @ScaledMetric(relativeTo: .title2) private var smallSize = 24

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            PlanCurrencyChoice(currency: $currency, locked: !currencySelectable,
                               spanish: spanish, showLock: showCurrencyLock)
            TextField("0", value: $value, format: .number.precision(.fractionLength(0...2)))
                .keyboardType(.decimalPad).focused($focused)
                .font(.system(size: prominent ? largeSize : smallSize, weight: .medium, design: .rounded))
                .monospacedDigit().multilineTextAlignment(.leading)
                .minimumScaleFactor(0.5).lineLimit(1)
                .tint(WelcomePalette.pine)
                .frame(minWidth: 0, maxWidth: .infinity, minHeight: 52)
                .overlay(alignment: .bottom) {
                    Rectangle().fill(focused ? WelcomePalette.pine : WelcomePalette.ink.opacity(0.12))
                        .frame(height: focused ? 2 : 1)
                }
                .accessibilityLabel(title).accessibilityIdentifier(identifier)
        }
    }
}
