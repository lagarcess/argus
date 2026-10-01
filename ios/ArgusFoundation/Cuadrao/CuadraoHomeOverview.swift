import SwiftUI
import Charts

struct CuadraoHomeOverview: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    var openPlan: () -> Void = {}
    @State private var chosenCurrency: String?
    @State private var distribution = false
    private var currencies: [String] { Set(data.active.map(\.currency)).sorted() }
    private var currency: String { chosenCurrency.flatMap { currencies.contains($0) ? $0 : nil } ?? currencies.first ?? "DOP" }
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Picker(spanish ? "Vista del balance" : "Balance view", selection: $distribution) {
                Text(spanish ? "Evolución" : "History").tag(false)
                Text(spanish ? "Distribución" : "Breakdown").tag(true)
            }.pickerStyle(.segmented).accessibilityIdentifier("home-chart-view")
            if distribution {
                CuadraoHomeDistribution(accounts: data.active.filter { $0.currency == currency },
                    currency: currency, spanish: spanish)
                if currencies.count > 1 {
                    Picker(spanish ? "Moneda" : "Currency", selection: Binding(get: { currency }, set: { chosenCurrency = $0 })) {
                        ForEach(currencies, id: \.self) { Text($0).tag($0) }
                    }.pickerStyle(.menu)
                }
            } else {
            CuadraoHomeBalanceChart(accounts: data.active.filter { $0.currency == currency },
                observations: data.balanceObservations, currency: currency, currencies: currencies,
                spanish: spanish, shared: data.selectedSpace.kind == .household,
                chooseCurrency: { chosenCurrency = $0 })
                .id(data.selectedSpaceID + currency)
            }
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
}

struct CuadraoHomeBalanceChart: View {
    let accounts: [CanvasAccount]
    let observations: [CanvasBalanceObservation]
    let currency: String
    let currencies: [String]
    let spanish: Bool
    let shared: Bool
    let chooseCurrency: (String) -> Void
    var expanded = false
    @State private var range: CanvasHistoryRange = .month
    @State private var month: Date?
    @State private var showHistory = false
    @State private var selectedDate: Date?
    private var history: [CanvasBalancePoint] { CanvasBalanceHistory.points(accounts: accounts, observations: observations, now: .now) }
    private var points: [CanvasBalancePoint] { range.points(history, month: month) }
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
            Text((selected ?? (month != nil ? shown : nil)).map { dateLabel($0.date) } ?? (partial
                 ? (spanish ? "Balance parcial · Faltan balances" : "Partial balance · Some balances missing")
                 : (shared ? (spanish ? "Balance de cuentas compartidas" : "Shared account balance")
                    : (spanish ? "Balance neto registrado" : "Recorded net balance"))))
                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                .accessibilityIdentifier("home-chart-date")
            if expanded { monthPicker }
            if points.count > 1 {
                chart
                HStack {
                    Text(dateLabel(points.first!.date))
                    Spacer()
                    if month != nil {
                        Text(dateLabel(points.last!.date)).frame(minHeight: 44)
                    } else {
                        Button { selectedDate = nil } label: { Text(spanish ? "Hoy" : "Today").frame(minHeight: 44) }
                            .buttonStyle(.plain).accessibilityIdentifier("home-chart-today")
                    }
                }.font(CuadraoTypography.caption).foregroundStyle(.secondary)
            } else {
                HStack(spacing: 12) {
                    Image(systemName: "chart.xyaxis.line").foregroundStyle(WelcomePalette.pine)
                    Text(spanish ? "Tu historia empieza aquí. La curva aparecerá con más balances registrados." : "Your story starts here. More recorded balances will build your chart.")
                        .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                }.padding(.vertical, 16).accessibilityIdentifier("home-chart-empty")
            }
            if month == nil {
                HStack(spacing: 0) {
                    ForEach(CanvasHistoryRange.allCases) { option in
                        Button {
                            range = option; selectedDate = nil
                        } label: {
                            Text(option.title(spanish)).font(CuadraoTypography.caption)
                                .frame(maxWidth: .infinity, minHeight: 44)
                                .background(range == option ? WelcomePalette.sage : .clear, in: Capsule())
                        }.buttonStyle(.plain).accessibilityIdentifier("home-range-" + option.rawValue)
                            .accessibilityAddTraits(range == option ? .isSelected : [])
                    }
                }
            }
            HStack {
                Text(spanish ? "Datos de ejemplo" : "Sample data").font(CuadraoTypography.caption).foregroundStyle(.secondary)
                Spacer()
                if !expanded {
                    Button { showHistory = true } label: {
                        Image(systemName: "arrow.up.left.and.arrow.down.right").frame(width: 44, height: 44)
                    }.buttonStyle(.plain).accessibilityLabel(spanish ? "Explorar historial" : "Explore history")
                        .accessibilityIdentifier("home-history-expand")
                }
            }
            if selected != nil && partial {
                Text(spanish ? "Balance parcial · Faltan balances" : "Partial balance · Some balances missing")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
        }.sensoryFeedback(.selection, trigger: selected?.date)
            .sheet(isPresented: $showHistory) {
                CuadraoHomeHistorySheet(accounts: accounts, observations: observations, currency: currency,
                    spanish: spanish, shared: shared)
            }
    }
    private var monthPicker: some View {
        Menu {
            Button(spanish ? "Hasta hoy" : "Through today") { month = nil; selectedDate = nil }
            ForEach(Array(Set(history.map { Calendar.current.dateInterval(of: .month, for: $0.date)!.start })).sorted(by: >), id: \.self) { date in
                Button(monthLabel(date)) { month = date; selectedDate = nil }
            }
        } label: {
            HStack {
                Text(month.map(monthLabel) ?? (spanish ? "Elegir un mes" : "Choose a month"))
                Image(systemName: "chevron.down").font(.caption)
            }.font(CuadraoTypography.supporting).frame(minHeight: 44)
        }.accessibilityIdentifier("home-history-month")
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
            .frame(height: expanded ? 270 : 125).accessibilityIdentifier("home-balance-chart")
    }
    private func monthLabel(_ date: Date) -> String {
        date.formatted(.dateTime.month(.wide).year().locale(Locale(identifier: spanish ? "es_DO" : "en_US")))
    }
    private func dateLabel(_ date: Date) -> String {
        date.formatted(.dateTime.day().month(.abbreviated).locale(Locale(identifier: spanish ? "es_DO" : "en_US")))
    }
}
