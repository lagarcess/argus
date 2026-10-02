import SwiftUI
import Charts

struct CuadraoSpendingChart: View {
    let expenses: [CanvasActivity]
    let coverageStart: Date?
    let currency: String
    let spanish: Bool
    let distribution: Bool
    let range: CanvasHistoryRange
    @Binding var periodOffset: Int
    var controls: CuadraoInsightControls?
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var selectedPosition: String?
    @State private var selectedCategory: CanvasExpenseCategory?
    private var story: CanvasSpendingStory { CanvasSpendingStory(expenses: expenses, range: range, offset: periodOffset, coverageStart: coverageStart) }
    private var interval: DateInterval { story.interval }
    private var entries: [CanvasActivity] { story.entries }
    private var total: Decimal { story.total }
    private var slots: [DateInterval] { CanvasSpendingHistory.slots(in: interval, range: range) }
    private var selectedSlot: DateInterval? {
        guard let selectedPosition, let index = slots.firstIndex(where: { tick($0) == selectedPosition }), slots[index].start <= story.now else { return nil }
        return slots[index]
    }
    private var buckets: [CanvasSpendingBucket] { CanvasSpendingHistory.buckets(entries, range: range) }
    private var categories: [CanvasExpenseCategory] { CanvasExpenseCategory.allCases.filter { categoryTotal($0) > 0 } }
    private var inspected: [CanvasActivity]? {
        guard let span = selectedSlot else { return nil }
        return CanvasSpendingHistory.entries(entries, in: span)
    }
    private func categoryTotal(_ category: CanvasExpenseCategory) -> Decimal {
        CanvasSpendingHistory.total(entries.filter { $0.category == category })
    }
    private func money(_ amount: Decimal) -> String { CanvasMoney.format(amount, currency: currency) }
    private var insight: String {
        guard story.covered else {
            return spanish ? "Este período tiene un historial incompleto." : "This period has incomplete history."
        }
        guard total > 0 else { return spanish ? "Aún no hay gastos registrados en este período." : "No expenses recorded in this period yet." }
        if let prior = story.previousTotal {
            let difference = total - prior
            if difference == 0 { return spanish ? "Has registrado el mismo gasto que en el período anterior." : "Your recorded spending matches the previous period." }
            let reference = periodOffset == 0 ? (spanish ? "al mismo punto del período anterior" : "at this point in the previous period") : (spanish ? "en el período anterior" : "in the previous period")
            return spanish ? "Llevas \(currency) \(money(abs(difference))) \(difference > 0 ? "más" : "menos") que \(reference)." : "You've spent \(currency) \(money(abs(difference))) \(difference > 0 ? "more" : "less") than \(reference)."
        }
        guard let largest = categories.max(by: { categoryTotal($0) < categoryTotal($1) }) else { return "" }
        return spanish ? "\(largest.title(true)) se lleva la mayor parte este período." : "\(largest.title(false)) takes the largest share this period."
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(currency).font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                    Text(entries.isEmpty && !story.covered ? "—" : money(inspected.map(CanvasSpendingHistory.total) ?? total))
                        .font(CuadraoTypography.amount).lineLimit(1).minimumScaleFactor(0.5)
                        .accessibilityIdentifier("home-spending-total")
                }
                Text(selectedSlot.map { range == .year ? $0.start.formatted(.dateTime.month(.wide).year().locale(Locale(identifier: spanish ? "es_DO" : "en_US"))) : story.periodText($0, spanish: spanish) } ?? (spanish ? "Gastos registrados" : "Recorded spending"))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                Text(insight).font(CuadraoTypography.supporting).fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("home-spending-insight")
            }
            if let controls { controls }
            if distribution { allocation } else { chart }
            ForEach(categories) { category in categoryRow(category) }
            CuadraoSpendingHighlights(story: story, currency: currency, spanish: spanish)
        }.onChange(of: range) { _, _ in clearSelection() }
            .onChange(of: periodOffset) { _, _ in clearSelection() }
            .onChange(of: distribution) { _, _ in clearSelection() }
            .sensoryFeedback(.selection, trigger: selectedSlot?.start)
            .sensoryFeedback(.selection, trigger: periodOffset)
    }
    private var chart: some View {
        Chart {
            ForEach(buckets) { bucket in
                BarMark(x: .value("Period", tick(CanvasSpendingHistory.bucketInterval(containing: bucket.date, range: range))), y: .value("Spending", bucket.value), width: .ratio(0.65))
                    .foregroundStyle(by: .value("Category", bucket.category.title(spanish)))
                    .accessibilityLabel(bucket.date.formatted(date: .abbreviated, time: .omitted) + ", " + bucket.category.title(spanish))
                    .accessibilityValue(currency + " " + money(bucket.amount))
            }
            if let selectedSlot {
                RuleMark(x: .value("Period", tick(selectedSlot))).foregroundStyle(WelcomePalette.ink.opacity(0.25))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 4])).accessibilityHidden(true)
            }
        }.chartForegroundStyleScale(domain: CanvasExpenseCategory.allCases.map { $0.title(spanish) }, range: CanvasExpenseCategory.allCases.map(\.color))
            .chartLegend(.hidden).chartXScale(domain: slots.map(tick))
            .chartYScale(domain: 0...max(1, peak * 1.15))
            .chartXAxis {
                AxisMarks(values: axisPositions) { value in
                    AxisTick()
                    AxisValueLabel {
                        if let position = value.as(String.self) { Text(position).font(.caption2).fixedSize(horizontal: true, vertical: true) }
                    }
                }
            }
            .chartXAxisLabel(position: .bottom, alignment: .leading) {
                Text(axisContext).font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            .chartYAxis {
                if entries.isEmpty { AxisMarks(position: .trailing, values: [0]) }
                else { AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) }
            }
            .chartOverlay { proxy in
                GeometryReader { geometry in
                    CuadraoChartTouchSurface(inspect: { inspect($0, proxy: proxy, geometry: geometry) })
                }
            }
            .frame(height: entries.isEmpty ? 170 : 270).padding(14)
            .overlay {
                if entries.isEmpty {
                    Image(systemName: "chart.bar.xaxis")
                        .font(.system(size: 32, weight: .light)).foregroundStyle(WelcomePalette.pine.opacity(0.5))
                        .allowsHitTesting(false).accessibilityHidden(true)
                }
            }
            .background(WelcomePalette.surface.opacity(0.5), in: RoundedRectangle(cornerRadius: 22))
            .accessibilityIdentifier("home-spending-chart")
            .accessibilityValue(String(periodOffset))
            .accessibilityLabel(entries.isEmpty ? insight : (spanish ? "Gastos por período" : "Spending by period"))
    }
    private func inspect(_ location: CGPoint, proxy: ChartProxy, geometry: GeometryProxy) {
        guard let frame = proxy.plotFrame else { return }
        let plot = geometry[frame]
        selectedPosition = proxy.value(atX: min(max(0, location.x - plot.minX), plot.width), as: String.self)
    }
    private var peak: Double {
        Dictionary(grouping: buckets, by: \.date).values.map { $0.reduce(0) { $0 + $1.value } }.max() ?? 0
    }
    private var axisContext: String {
        let format = Date.FormatStyle.dateTime.locale(Locale(identifier: spanish ? "es_DO" : "en_US"))
        if range == .year { return interval.start.formatted(format.year()) }
        let start = interval.start.formatted(format.month(.abbreviated).year())
        let end = interval.end.addingTimeInterval(-1).formatted(format.month(.abbreviated).year())
        return start == end ? start : start + " – " + end
    }
    private var axisPositions: [String] {
        let step = range == .year ? (typeSize.isAccessibilitySize ? 3 : 2) : (range == .month && typeSize.isAccessibilitySize ? 2 : 1)
        return stride(from: 0, to: slots.count, by: step).map { tick(slots[$0]) }
    }
    private func tick(_ span: DateInterval) -> String {
        let format = Date.FormatStyle.dateTime.locale(Locale(identifier: spanish ? "es_DO" : "en_US"))
        switch range {
        case .week: return span.start.formatted(format.weekday(.narrow)) + "\n" + span.start.formatted(format.day())
        case .month:
            let first = span.start.formatted(format.day())
            let last = span.end.addingTimeInterval(-1).formatted(format.day())
            return first == last ? first : first + "–" + last
        case .year: return span.start.formatted(format.month(.abbreviated))
        }
    }
    private var allocation: some View {
        VStack(alignment: .leading, spacing: 12) {
            CuadraoAllocationBar(segments: categories.map {
                CuadraoAllocationSegment(id: $0.rawValue, title: $0.title(spanish), fraction: fraction(categoryTotal($0)), color: $0.color)
            }, selection: Binding(get: { selectedCategory?.rawValue }, set: { selectedCategory = $0.flatMap(CanvasExpenseCategory.init(rawValue:)) }),
                identifier: "home-spending-segment-")
            if selectedCategory != nil {
                Button(spanish ? "Todo" : "All") { selectedCategory = nil }.frame(minHeight: 44)
            }
            HStack {
                Text(interval.start, format: .dateTime.day().month(.abbreviated).year())
                Spacer()
                Text(interval.end.addingTimeInterval(-1), format: .dateTime.day().month(.abbreviated).year())
            }.font(CuadraoTypography.caption).foregroundStyle(.secondary)
        }.padding(.vertical, 20)
            .overlay { CuadraoChartTouchSurface(inspect: { _ in }) }
            .accessibilityIdentifier("home-spending-distribution")
    }
    private func categoryRow(_ category: CanvasExpenseCategory) -> some View {
        DisclosureGroup(isExpanded: Binding(get: { selectedCategory == category }, set: { selectedCategory = $0 ? category : nil })) {
            LazyVStack(spacing: 0) {
            ForEach(entries.filter { $0.category == category }.sorted { $0.date > $1.date }) { entry in
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(entry.title).font(CuadraoTypography.supporting)
                        Text(entry.date, format: .dateTime.day().month(.abbreviated)).font(CuadraoTypography.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text(money(entry.amount)).font(CuadraoTypography.rowAmount)
                }.padding(.vertical, 8)
            }
            }
        } label: {
            HStack(spacing: 12) {
                CuadraoExpenseCategoryIcon(category: category)
                Text(category.title(spanish)).font(CuadraoTypography.supporting)
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 4) {
                    Text(money(categoryTotal(category))).font(CuadraoTypography.rowAmount)
                    Text(fraction(categoryTotal(category)), format: .percent.precision(.fractionLength(1)))
                        .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                }
            }.frame(minHeight: 44)
        }.accessibilityIdentifier("home-spending-category-" + category.rawValue)
    }
    private func fraction(_ value: Decimal) -> Double { total > 0 ? NSDecimalNumber(decimal: value / total).doubleValue : 0 }
    private func clearSelection() { selectedPosition = nil; selectedCategory = nil }
}
