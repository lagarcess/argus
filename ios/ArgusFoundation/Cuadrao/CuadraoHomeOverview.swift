import SwiftUI
import Charts

struct CuadraoHomeOverview: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    var openPlan: () -> Void = {}
    @State private var chosenCurrency: String?
    private var currencies: [String] { Set(data.active.map(\.currency)).sorted() }
    private var currency: String { chosenCurrency.flatMap { currencies.contains($0) ? $0 : nil } ?? currencies.first ?? "DOP" }
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(title).font(CuadraoTypography.screen).fixedSize(horizontal: false, vertical: true)
            CuadraoHomeBalanceChart(accounts: data.active.filter { $0.currency == currency },
                observations: data.balanceObservations, currency: currency, currencies: currencies,
                spanish: spanish, shared: data.selectedSpace.kind == .household,
                chooseCurrency: { chosenCurrency = $0 })
                .id(data.selectedSpaceID + currency)
            Button(action: openPlan) {
                HStack {
                    Text(spanish ? "¿Y lo que viene?" : "What comes next?")
                    Spacer()
                    Image(systemName: "arrow.up.right")
                }.font(CuadraoTypography.supporting).frame(minHeight: 44).contentShape(Rectangle())
            }.buttonStyle(.plain).accessibilityLabel(spanish ? "Explorar Plan" : "Explore Plan")
                .accessibilityIdentifier("home-chart-plan")
        }
    }
    private var title: String {
        if data.selectedSpace.kind == .household { return spanish ? "Lo de ustedes." : "Your shared picture." }
        if data.selectedSpace.kind != .personal { return data.selectedSpace.title(spanish) }
        return data.active.isEmpty ? (spanish ? "Un lugar para\ntus finanzas." : "A place for\nyour finances.")
            : (spanish ? "Tu panorama." : "Your overview.")
    }
}

private struct CuadraoHomeBalanceChart: View {
    let accounts: [CanvasAccount]
    let observations: [CanvasBalanceObservation]
    let currency: String
    let currencies: [String]
    let spanish: Bool
    let shared: Bool
    let chooseCurrency: (String) -> Void
    @State private var selectedDate: Date?
    private var points: [CanvasBalancePoint] { CanvasBalanceHistory.points(accounts: accounts, observations: observations, now: .now) }
    private var selected: CanvasBalancePoint? {
        guard let selectedDate else { return nil }
        return points.min { abs($0.date.timeIntervalSince(selectedDate)) < abs($1.date.timeIntervalSince(selectedDate)) }
    }
    private var shown: CanvasBalancePoint? { selected ?? points.last }
    private var partial: Bool { accounts.contains { $0.balance == nil } }
    private var bounds: ClosedRange<Double> {
        let values = points.map(\.value)
        let low = values.min() ?? 0, high = values.max() ?? 1
        let step = pow(10, floor(log10(max(high - low, max(abs(high) * 0.01, 1)))))
        return (floor((low - step * 0.2) / step) * step)...(ceil((high + step * 0.2) / step) * step)
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                if currencies.count > 1 {
                    Menu {
                        ForEach(currencies, id: \.self) { code in Button(code) { selectedDate = nil; chooseCurrency(code) } }
                    } label: {
                        HStack(spacing: 4) { Text(currency); Image(systemName: "chevron.down").font(.caption2) }.frame(minHeight: 44)
                    }.accessibilityIdentifier("home-chart-currency")
                } else { Text(currency).foregroundStyle(.secondary) }
                Text(shown.map { CanvasMoney.format($0.balance, currency: currency) } ?? "—")
                    .font(CuadraoTypography.amount).lineLimit(1).minimumScaleFactor(0.5)
                    .accessibilityIdentifier("home-chart-amount")
            }.font(CuadraoTypography.supporting)
            Text(selected.map { dateLabel($0.date) } ?? (partial
                 ? (spanish ? "Balance parcial · Faltan balances" : "Partial balance · Some balances missing")
                 : (shared ? (spanish ? "Balance de cuentas compartidas" : "Shared account balance")
                    : (spanish ? "Balance registrado" : "Recorded balance"))))
                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                .accessibilityIdentifier("home-chart-date")
            if points.count > 1 {
                chart
                HStack {
                    Text(dateLabel(points.first!.date))
                    Spacer()
                    Button { selectedDate = nil } label: { Text(spanish ? "Hoy" : "Today").frame(minHeight: 44) }
                        .buttonStyle(.plain).accessibilityIdentifier("home-chart-today")
                }.font(CuadraoTypography.caption).foregroundStyle(.secondary)
                Text(spanish ? "Últimos 30 días · Datos de ejemplo" : "Last 30 days · Sample data")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            } else {
                HStack(spacing: 12) {
                    Image(systemName: "chart.xyaxis.line").foregroundStyle(WelcomePalette.pine)
                    Text(spanish ? "Tu historia empieza aquí. La curva aparecerá con más balances registrados." : "Your story starts here. More recorded balances will build your chart.")
                        .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                }.padding(.vertical, 16).accessibilityIdentifier("home-chart-empty")
            }
            if selected != nil && partial {
                Text(spanish ? "Balance parcial · Faltan balances" : "Partial balance · Some balances missing")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
        }.sensoryFeedback(.selection, trigger: selected?.date)
    }
    private var chart: some View {
        Chart {
            ForEach(points) { point in
                AreaMark(x: .value("Date", point.date), yStart: .value("Base", bounds.lowerBound), yEnd: .value("Balance", point.value))
                    .foregroundStyle(LinearGradient(colors: [WelcomePalette.pine.opacity(0.16), WelcomePalette.pine.opacity(0)], startPoint: .top, endPoint: .bottom))
                    .accessibilityHidden(true)
                LineMark(x: .value(spanish ? "Fecha" : "Date", point.date), y: .value(spanish ? "Balance" : "Balance", point.value))
                    .lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round)).foregroundStyle(WelcomePalette.pine)
                    .accessibilityLabel(dateLabel(point.date)).accessibilityValue(currency + " " + CanvasMoney.format(point.balance, currency: currency))
            }
            if let point = shown {
                if selected != nil {
                    RuleMark(x: .value("Date", point.date)).lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 4]))
                        .foregroundStyle(WelcomePalette.ink.opacity(0.22)).accessibilityHidden(true)
                }
                PointMark(x: .value("Date", point.date), y: .value("Balance", point.value))
                    .symbolSize(selected == nil ? 32 : 65).foregroundStyle(WelcomePalette.pine).accessibilityHidden(true)
            }
        }.chartYScale(domain: bounds).chartXAxis(.hidden)
            .chartYAxis {
                AxisMarks(position: .trailing, values: [bounds.lowerBound, bounds.upperBound]) { value in
                    AxisValueLabel {
                        if let amount = value.as(Double.self) {
                            Text(amount.formatted(.number.precision(.fractionLength(0)).locale(Locale(identifier: "en_US"))))
                                .font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .chartXSelection(value: $selectedDate)
            .chartGesture { proxy in
                SpatialTapGesture().onEnded { proxy.selectXValue(at: $0.location.x) }
                    .exclusively(before: LongPressGesture(minimumDuration: 0.2)
                        .sequenced(before: DragGesture(minimumDistance: 0))
                        .onChanged { value in
                            if case .second(true, let drag?) = value { proxy.selectXValue(at: drag.location.x) }
                        })
            }
            .frame(height: 125).accessibilityIdentifier("home-balance-chart")
    }
    private func dateLabel(_ date: Date) -> String {
        date.formatted(.dateTime.day().month(.abbreviated).locale(Locale(identifier: spanish ? "es_DO" : "en_US")))
    }
}
