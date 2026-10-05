import SwiftUI
import ArgusSession

struct FinancialPlanForecast<Details: View>: View {
    let projection: FinancialPlanProjection
    let chooseAccounts: () -> Void
    var canChooseAccounts = true
    var bottomSpace: CGFloat = 90
    @ViewBuilder let details: () -> Details
    @State private var selectedCurrency: String?
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private var currency: FinancialForecastCurrency? {
        projection.currencies.first { $0.currency == selectedCurrency } ?? projection.currencies.first
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            CuadraoPlanForecastSection(period: spanish ? "Tu previsión" : "Your forecast") {
                if projection.currencies.count > 1 {
                    CuadraoChoiceMenu(title: NSLocalizedString("accounts.currency", comment: ""),
                        selection: Binding(get: { currency?.currency ?? "" }, set: { selectedCurrency = $0 }),
                        values: projection.currencies.map(\.currency), valueTitle: { $0 })
                        .accessibilityIdentifier("plan.forecast.currency")
                } else {
                    CuadraoChoiceLabel(title: NSLocalizedString("context.personal", comment: ""), selectable: false)
                }
            } content: {
                if let currency {
                    FinancialPlanForecastCurrency(currency: currency, start: projection.startDate, end: projection.endDate)
                        .id(currency.currency)
                    Text(spanish ? "Según tus saldos y compromisos registrados. No estima gastos sin programar." : "Based on your balances and scheduled items. Unplanned spending is not estimated.")
                        .font(.caption).foregroundStyle(.secondary).accessibilityIdentifier("plan.coverage")
                } else {
                    CuadraoPlanColdStart(spanish: spanish,
                        detail: spanish ? "Puedes hacer tu primer plan hoy. Elige las cuentas que quieres incluir para ver lo que viene." : "Make your first plan today. Choose the accounts to include to see what's ahead.") {
                        Button("plan.chooseMoney", action: chooseAccounts).disabled(!canChooseAccounts)
                            .accessibilityIdentifier("plan.chooseAccounts")
                    }
                }
            } explore: {
                #if DEBUG
                CuadraoPlanExploreLink(spanish: spanish, example: true) {
                    FinancialPlanScenarioExample(spanish: spanish, bottomSpace: bottomSpace)
                }
                #endif
            }
            DisclosureGroup {
                VStack(alignment: .leading, spacing: 16) {
                    if let currency {
                        PlanValueRow(title: "plan.income", value: amount(currency.expectedIncomeMinor, in: currency))
                        PlanValueRow(title: "plan.bills", value: amount(currency.expectedBillsMinor, in: currency))
                        if let effect = currency.transferEffectMinor {
                            PlanValueRow(title: "goal.transferEffect", value: amount(effect, in: currency))
                        }
                        PlanValueRow(title: "plan.netChange", value: amount(currency.netCashChangeMinor, in: currency))
                        if let asOf = currency.asOf {
                            Text(NSLocalizedString("plan.asOf", comment: "") + " " + AccountPresentation.date(asOf, zone: projection.selection.timeZone, locale: locale))
                                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                        }
                    }
                    details()
                    Text("plan.assumptions").font(CuadraoTypography.caption).foregroundStyle(.secondary)
                }.padding(.top, 16)
            } label: {
                Text(spanish ? "¿De dónde sale?" : "What's behind this?").font(.subheadline.weight(.medium))
                    .accessibilityIdentifier("plan.forecast.details")
            }.padding(.top, 8)
        }
    }
    private func amount(_ minor: String, in currency: FinancialForecastCurrency) -> String {
        PlanPresentation.money(minor, currency: currency.currency, digits: currency.currencyFractionDigits, locale: locale)
    }
}

#if DEBUG
private struct FinancialPlanScenarioExample: View {
    let spanish: Bool
    let bottomSpace: CGFloat
    @State private var example: CuadraoPlanPreview

    init(spanish: Bool, bottomSpace: CGFloat) {
        self.spanish = spanish; self.bottomSpace = bottomSpace
        _example = State(initialValue: CuadraoPlanPreview(spanish: spanish, defaults: nil, reset: true))
    }

    var body: some View {
        CuadraoForecastPlayground(store: example, scope: CanvasSpace.personalID,
            scopeName: spanish ? "Ejemplo" : "Example", spanish: spanish,
            bottomSpace: bottomSpace, isolatedExample: true)
    }
}
#endif

private struct FinancialPlanForecastCurrency: View {
    let currency: FinancialForecastCurrency
    let start: String
    let end: String
    @State private var selected: Int?
    @Environment(\.locale) private var locale
    private var selectedPoint: FinancialForecastCurrency.Point? {
        guard let selected, currency.points.indices.contains(selected) else { return nil }
        return currency.points[selected]
    }
    private var displayedMinor: String? {
        if let selectedPoint { return selectedPoint.balanceMinor }
        return currency.endingMinor
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            CuadraoPlanForecastValue(
                title: selectedPoint.map { PlanPresentation.dateLabel($0.date, locale: locale) + " · " + NSLocalizedString("plan.projectedBalance", comment: "") } ?? NSLocalizedString("plan.projectedBalance", comment: ""),
                amount: displayedMinor.map(amount) ?? currency.currency + " · " + NSLocalizedString("accounts.unknown", comment: ""),
                identifier: (displayedMinor == nil ? "plan.unknown." : "plan.projected.") + currency.currency)
            if !currency.unknownAccountIds.isEmpty {
                if currency.accountIds.contains(where: { !currency.unknownAccountIds.contains($0) }) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(locale.language.languageCode?.identifier == "es" ? "Saldo inicial conocido" : "Known starting balance")
                        Text(amount(currency.knownStartingMinor)).monospacedDigit()
                            .accessibilityIdentifier("plan.knownStarting." + currency.currency)
                    }.font(CuadraoTypography.supporting)
                }
                Text("\(currency.unknownAccountIds.count) · " + NSLocalizedString("accounts.unknown", comment: ""))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            if currency.unknownAccountIds.isEmpty, currency.points.allSatisfy({ $0.balanceMinor != nil }), !currency.points.isEmpty {
                FinancialForecastChart(currency: currency, start: start, end: end, selected: $selected)
            } else {
                Text(PlanPresentation.dateLabel(start, locale: locale) + " · " + PlanPresentation.dateLabel(end, locale: locale))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                CuadraoChartState(title: NSLocalizedString("accounts.unknown", comment: ""),
                    detail: NSLocalizedString("plan.unknown", comment: ""))
            }
            if let shortfall = currency.firstShortfallDate {
                Label { Text("plan.shortfall") + Text(verbatim: " · " + PlanPresentation.dateLabel(shortfall, locale: locale)) }
                    icon: { Image(systemName: "exclamationmark.circle") }
                    .font(CuadraoTypography.supporting).accessibilityIdentifier("plan.shortfall." + currency.currency)
            }
        }
        .onChange(of: start) { _, _ in selected = nil }
        .onChange(of: end) { _, _ in selected = nil }
        .onChange(of: currency.points.count) { _, _ in selected = nil }
    }
    private func amount(_ minor: String) -> String {
        PlanPresentation.money(minor, currency: currency.currency, digits: currency.currencyFractionDigits, locale: locale)
    }
}

struct FinancialForecastChart: View {
    let currency: FinancialForecastCurrency
    let start: String
    let end: String
    @Binding var selected: Int?
    @Environment(\.locale) private var locale
    private var points: [CuadraoPlanChartPoint] {
        currency.points.enumerated().compactMap { index, point in
            guard let minor = point.balanceMinor, let value = Double(minor) else { return nil }
            return .init(id: index, position: PlanPresentation.date(point.date).timeIntervalSince1970, balance: value)
        }
    }
    private var yRange: ClosedRange<Double> {
        let values = points.map(\.balance)
        let low = values.min() ?? 0, high = values.max() ?? 0
        let padding = max((high - low) * 0.1, max(abs(low), abs(high)) * 0.02, 1)
        return (low - padding)...(high + padding)
    }
    private var xRange: ClosedRange<Double> {
        let first = PlanPresentation.date(start).timeIntervalSince1970
        let last = PlanPresentation.date(end).timeIntervalSince1970
        return first == last ? (first - 43200)...(last + 43200) : first...last
    }
    private var ticks: [CuadraoPlanChartTick] {
        Array(Set([start, end])).sorted().map {
            .init(position: PlanPresentation.date($0).timeIntervalSince1970, title: PlanPresentation.dateLabel($0, locale: locale))
        }
    }
    private var readout: String? {
        guard let selected, currency.points.indices.contains(selected), let minor = currency.points[selected].balanceMinor else { return nil }
        return PlanPresentation.dateLabel(currency.points[selected].date, locale: locale) + " · " +
            PlanPresentation.money(minor, currency: currency.currency, digits: currency.currencyFractionDigits, locale: locale)
    }

    var body: some View {
        CuadraoPlanForecastChart(recorded: [], projected: points, xRange: xRange, yRange: yRange,
            ticks: ticks, selected: points.first { $0.id == selected },
            selection: Binding(get: { points.first { $0.id == selected }?.position }, set: { position in
                selected = position.flatMap { value in points.reversed().min { abs($0.position - value) < abs($1.position - value) }?.id }
            }), compact: true, identifier: "plan.chart",
            accessibilityTitle: NSLocalizedString("plan.chart.title", comment: ""),
            accessibilityAmount: readout ?? currency.endingMinor.map { PlanPresentation.money($0, currency: currency.currency, digits: currency.currencyFractionDigits, locale: locale) } ?? "")
            .accessibilityHint(Text("plan.chart.accessibility"))
            .accessibilityAdjustableAction { direction in
                switch direction {
                case .increment: selected = min((selected ?? 0) + 1, max(0, currency.points.count - 1))
                case .decrement: selected = max((selected ?? 0) - 1, 0)
                @unknown default: break
                }
            }
    }
}
