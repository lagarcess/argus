import SwiftUI
import Charts

struct CuadraoHomeBalanceChart: View {
    let accounts: [CanvasAccount]
    let observations: [CanvasBalanceObservation]
    let currency: String
    let currencies: [String]
    let spanish: Bool
    let shared: Bool
    let chooseCurrency: (String) -> Void
    var expanded = false
    var expand: () -> Void = {}
    var viewChoice: CuadraoChartViewChoice?
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var compactRange: CanvasHomeRange = .month
    @Binding var range: CanvasHistoryRange
    @Binding var periodOffset: Int
    @State private var selectedDate: Date?
    init(accounts: [CanvasAccount], observations: [CanvasBalanceObservation], currency: String,
         currencies: [String], spanish: Bool, shared: Bool, chooseCurrency: @escaping (String) -> Void,
         expanded: Bool = false, expand: @escaping () -> Void = {}, viewChoice: CuadraoChartViewChoice? = nil,
         range: Binding<CanvasHistoryRange> = .constant(.month), periodOffset: Binding<Int> = .constant(0)) {
        self.accounts = accounts; self.observations = observations; self.currency = currency
        self.currencies = currencies; self.spanish = spanish; self.shared = shared; self.chooseCurrency = chooseCurrency
        self.expanded = expanded; self.expand = expand; self.viewChoice = viewChoice
        _range = range; _periodOffset = periodOffset
    }
    private var history: [CanvasBalancePoint] { CanvasBalanceHistory.points(accounts: accounts, observations: observations, now: .now) }
    private var availableRanges: [CanvasHomeRange] { CanvasHomeRange.available(history) }
    private var effectiveRange: CanvasHomeRange { availableRanges.contains(compactRange) ? compactRange : .all }
    private var points: [CanvasBalancePoint] {
        expanded ? range.points(history, offset: periodOffset) : effectiveRange.points(history)
    }
    private var xDomain: ClosedRange<Date> {
        if expanded {
            let interval = range.interval(offset: periodOffset)
            return interval.start...interval.end
        }
        let first = points.first?.date ?? Date.now
        return first...max(points.last?.date ?? first, first.addingTimeInterval(86400))
    }
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
            amountRow
            if expanded && typeSize.isAccessibilitySize, let viewChoice { viewChoice }
            Text((expanded ? nil : selected.map { dateLabel($0.date) }) ?? (partial
                ? (spanish ? "Balance parcial" : "Partial balance")
                : (spanish ? "Balance neto" : "Net balance")))
                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                .accessibilityIdentifier("home-chart-date")
            if expanded, let point = shown {
                if selected != nil {
                    Text(dateLabel(point.date)).font(CuadraoTypography.caption).foregroundStyle(.secondary)
                }
                Text(takeaway(point)).font(CuadraoTypography.supporting)
                    .fixedSize(horizontal: false, vertical: true).accessibilityIdentifier("home-chart-takeaway")
            }
            if expanded {
                CuadraoHistoryPeriodChoice(range: $range, spanish: spanish)
                    .padding(.top, 8)
                    .onChange(of: range) { _, _ in periodOffset = 0; selectedDate = nil }
                periodHeading
            }
            if !points.isEmpty {
                periodCanvas
                HStack {
                    Text(dateLabel(expanded ? xDomain.lowerBound : points.first!.date))
                    Spacer()
                    if selectedDate != nil && !expanded {
                        Button(spanish ? "Hoy" : "Today") { selectedDate = nil }
                            .frame(minHeight: 44).accessibilityIdentifier("home-chart-today")
                    } else { Text(dateLabel(expanded ? xDomain.upperBound.addingTimeInterval(-1) : points.last!.date)) }
                }.font(CuadraoTypography.caption).foregroundStyle(.secondary)
            } else {
                Text(spanish ? "No hay balances en este período." : "No balances in this period.")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: expanded ? 270 : 125)
                    .contentShape(Rectangle()).gesture(periodSwipe)
                    .accessibilityIdentifier("home-chart-empty")
            }
            if !expanded && availableRanges.count > 1 {
                HStack(spacing: 2) {
                    ForEach(availableRanges) { option in
                        Button {
                            compactRange = option; selectedDate = nil
                        } label: {
                            Text(option.title(spanish)).font(CuadraoTypography.caption)
                                .frame(maxWidth: .infinity, minHeight: 44)
                                .background(effectiveRange == option ? WelcomePalette.sage : .clear, in: Capsule())
                                .contentShape(Rectangle())
                        }.buttonStyle(.plain).accessibilityIdentifier("home-range-" + option.rawValue)
                            .accessibilityAddTraits(effectiveRange == option ? .isSelected : [])
                    }
                }
            }
        }.onAppear { periodOffset = max(range.oldestOffset(history), min(0, periodOffset)) }
            .sensoryFeedback(.selection, trigger: selected?.date)
            .sensoryFeedback(.selection, trigger: periodOffset)
    }
    private var amountRow: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
                if currencies.count > 1 {
                    CuadraoChoiceMenu(title: spanish ? "Moneda" : "Currency",
                        selection: Binding(get: { currency }, set: { selectedDate = nil; chooseCurrency($0) }),
                        values: currencies, valueTitle: { $0 })
                        .accessibilityIdentifier("home-chart-currency")
                } else { Text(currency).foregroundStyle(.secondary) }
                Text(shown.map { CanvasMoney.format($0.balance, currency: currency) } ?? "—")
                    .font(CuadraoTypography.amount).lineLimit(1).minimumScaleFactor(0.5)
                    .accessibilityIdentifier("home-chart-amount")
                if expanded && !typeSize.isAccessibilitySize, let viewChoice {
                    Spacer(minLength: 8); viewChoice
                }
                if !expanded {
                    Spacer(minLength: 0)
                    Button(action: expand) {
                        Image(systemName: "arrow.up.left.and.arrow.down.right").font(.body)
                            .frame(width: 44, height: 44).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityLabel(spanish ? "Explorar balance" : "Explore balance")
                        .accessibilityIdentifier("home-history-expand")
                }
            }.font(CuadraoTypography.supporting)
    }
    private var periodCanvas: some View {
        chart.padding(expanded ? 14 : 0)
            .background {
                if expanded { RoundedRectangle(cornerRadius: 22).fill(WelcomePalette.surface.opacity(0.5)) }
            }
            .overlay(alignment: .leading) {
                if expanded && periodOffset > range.oldestOffset(history) { pageEdge.offset(x: -192) }
            }
            .overlay(alignment: .trailing) {
                if expanded && periodOffset < 0 { pageEdge.offset(x: 192) }
            }
    }
    private var pageEdge: some View {
        RoundedRectangle(cornerRadius: 22).fill(WelcomePalette.surface)
            .overlay { RoundedRectangle(cornerRadius: 22).stroke(WelcomePalette.border, lineWidth: 0.5) }
            .frame(width: 180, height: 258).allowsHitTesting(false).accessibilityHidden(true)
    }
    private var periodTitle: String {
        let interval = range.interval(offset: periodOffset)
        let format = Date.FormatStyle.dateTime.locale(Locale(identifier: spanish ? "es_DO" : "en_US"))
        switch range {
        case .month: return interval.start.formatted(format.month(.wide).year())
        case .year: return interval.start.formatted(format.year())
        case .week:
            let end = Calendar.current.date(byAdding: .day, value: -1, to: interval.end)!
            return dateLabel(interval.start) + " – " + dateLabel(end)
        }
    }
    private var periodHeading: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 4) {
                Text(periodTitle).font(CuadraoTypography.supporting).fontWeight(.medium)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityIdentifier("home-history-period")
                periodButton(-1)
                periodButton(1)
            }
            if periodOffset < 0 || selectedDate != nil {
                Button(spanish ? "Volver a hoy" : "Back to today") { periodOffset = 0; selectedDate = nil }
                    .font(CuadraoTypography.caption).frame(minHeight: 44).accessibilityIdentifier("home-chart-today")
            }
        }.frame(minHeight: 44).contentShape(Rectangle()).gesture(periodSwipe)
            .accessibilityAction(named: Text(spanish ? "Período anterior" : "Previous period")) { movePeriod(-1) }
            .accessibilityAction(named: Text(spanish ? "Período siguiente" : "Next period")) { movePeriod(1) }
    }
    private func periodButton(_ direction: Int) -> some View {
        Button { movePeriod(direction) } label: {
            Image(systemName: direction < 0 ? "chevron.left" : "chevron.right")
                .font(.subheadline.weight(.medium)).frame(width: 44, height: 44)
        }.buttonStyle(.plain)
            .disabled(direction < 0 ? periodOffset <= range.oldestOffset(history) : periodOffset >= 0)
            .accessibilityLabel(direction < 0 ? (spanish ? "Período anterior" : "Previous period") : (spanish ? "Período siguiente" : "Next period"))
            .accessibilityIdentifier(direction < 0 ? "home-period-previous" : "home-period-next")
    }
    private var periodSwipe: some Gesture {
        DragGesture(minimumDistance: 25).onEnded { value in
            guard abs(value.translation.width) > abs(value.translation.height) * 1.4 else { return }
            movePeriod(value.translation.width > 0 ? -1 : 1)
        }
    }
    private func movePeriod(_ direction: Int) {
        guard expanded else { return }
        let next = min(0, max(range.oldestOffset(history), periodOffset + direction))
        guard next != periodOffset else { return }
        selectedDate = nil
        periodOffset = next
    }
    private func takeaway(_ point: CanvasBalancePoint) -> String {
        guard let baseline = range.baseline(history, offset: periodOffset), baseline.date < point.date else {
            return spanish ? "Aquí empieza este período." : "This is where this period begins."
        }
        let change = point.balance - baseline.balance
        if change == 0 { return spanish ? "Tu balance sigue igual desde el \(dateLabel(baseline.date))." : "Your balance is unchanged since \(dateLabel(baseline.date))." }
        let amount = currency + " " + CanvasMoney.format(abs(change), currency: currency)
        if spanish { return "\(amount) \(change > 0 ? "más" : "menos") desde el \(dateLabel(baseline.date))." }
        return "\(amount) \(change > 0 ? "more" : "less") since \(dateLabel(baseline.date))."
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
        }.chartYScale(domain: bounds)
            .chartXScale(domain: xDomain)
            .chartXAxis(.hidden)
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
                LongPressGesture(minimumDuration: 0.2)
                    .sequenced(before: DragGesture(minimumDistance: 0))
                    .onChanged { value in
                        if case .second(true, let drag?) = value { proxy.selectXValue(at: drag.location.x) }
                    }
                    .exclusively(before: periodSwipe)
                    .simultaneously(with: SpatialTapGesture().onEnded { proxy.selectXValue(at: $0.location.x) })
            }
            .frame(height: expanded ? 270 : 125).accessibilityIdentifier("home-balance-chart")
    }
    private func dateLabel(_ date: Date) -> String {
        date.formatted(.dateTime.day().month(.abbreviated).locale(Locale(identifier: spanish ? "es_DO" : "en_US")))
    }
}
