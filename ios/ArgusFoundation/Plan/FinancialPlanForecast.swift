import SwiftUI
import ArgusSession

struct FinancialPlanForecast: View {
    let projection: FinancialPlanProjection
    @State private var selectedCurrency: String?
    @Environment(\.locale) private var locale
    private var currency: FinancialForecastCurrency? {
        projection.currencies.first { $0.currency == selectedCurrency } ?? projection.currencies.first
    }
    private var period: String {
        PlanPresentation.dateLabel(projection.startDate, locale: locale) + " – " +
            PlanPresentation.dateLabel(projection.endDate, locale: locale)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            CuadraoPlanForecastHeading(period: period) {
                if projection.currencies.count > 1 {
                    CuadraoChoiceMenu(title: NSLocalizedString("accounts.currency", comment: ""),
                        selection: Binding(get: { currency?.currency ?? "" }, set: { selectedCurrency = $0 }),
                        values: projection.currencies.map(\.currency), valueTitle: { $0 })
                        .accessibilityIdentifier("plan.forecast.currency")
                } else {
                    CuadraoChoiceLabel(title: NSLocalizedString("context.personal", comment: ""), selectable: false)
                }
            }
            if let currency {
                FinancialPlanForecastCurrency(currency: currency, start: projection.startDate, end: projection.endDate)
                    .id(currency.currency)
            } else {
                CuadraoChartState(title: NSLocalizedString("plan.chooseMoney", comment: ""),
                    detail: NSLocalizedString("plan.selection.hint", comment: ""))
            }
        }
    }
}

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
                Text("plan.unknown").font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                VStack(alignment: .leading, spacing: 4) {
                    Text(locale.language.languageCode?.identifier == "es" ? "Saldo inicial conocido" : "Known starting balance")
                    Text(amount(currency.knownStartingMinor)).monospacedDigit()
                }.font(CuadraoTypography.supporting)
                Text("\(currency.unknownAccountIds.count) · " + NSLocalizedString("accounts.unknown", comment: ""))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            if let asOf = currency.asOf {
                Text(NSLocalizedString("plan.asOf", comment: "") + " " + AccountPresentation.date(asOf, zone: TimeZone.current.identifier, locale: locale))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            if currency.unknownAccountIds.isEmpty, currency.points.allSatisfy({ $0.balanceMinor != nil }), !currency.points.isEmpty {
                FinancialForecastChart(currency: currency, start: start, end: end, selected: $selected)
            } else {
                CuadraoChartState(title: NSLocalizedString("accounts.unknown", comment: ""),
                    detail: NSLocalizedString("plan.unknown", comment: ""))
            }
            DisclosureGroup("plan.overview") {
                VStack(alignment: .leading, spacing: 12) {
                    PlanValueRow(title: "plan.income", value: amount(currency.expectedIncomeMinor))
                    PlanValueRow(title: "plan.bills", value: amount(currency.expectedBillsMinor))
                    if let effect = currency.transferEffectMinor { PlanValueRow(title: "goal.transferEffect", value: amount(effect)) }
                    PlanValueRow(title: "plan.netChange", value: amount(currency.netCashChangeMinor))
                }.padding(.top, 12)
            }.font(CuadraoTypography.supporting).padding(.top, 8)
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
        VStack(alignment: .leading, spacing: 12) {
            CuadraoPlanForecastChart(recorded: [], projected: points, xRange: xRange, yRange: yRange,
                ticks: ticks, selected: points.first { $0.id == selected },
                selection: Binding(get: { points.first { $0.id == selected }?.position }, set: { position in
                    selected = position.flatMap { value in points.reversed().min { abs($0.position - value) < abs($1.position - value) }?.id }
                }), compact: true, identifier: "plan.chart",
                accessibilityTitle: NSLocalizedString("plan.chart.title", comment: ""),
                accessibilityAmount: readout ?? currency.endingMinor.map { PlanPresentation.money($0, currency: currency.currency, digits: currency.currencyFractionDigits, locale: locale) } ?? "")
            if let readout {
                Text(readout).font(CuadraoTypography.supporting).monospacedDigit().accessibilityIdentifier("plan.chart.readout")
            } else {
                Text("plan.chart.title").font(CuadraoTypography.supporting).foregroundStyle(.secondary)
            }
            Stepper("plan.chart.accessibility", value: Binding(get: { selected ?? 0 }, set: { selected = $0 }), in: 0...max(0, currency.points.count - 1))
                .font(CuadraoTypography.supporting).accessibilityIdentifier("plan.chart.step")
        }
    }
}
