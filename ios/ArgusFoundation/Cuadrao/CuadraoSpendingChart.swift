import SwiftUI
import Charts

extension CanvasExpenseCategory {
    var color: Color {
        switch self {
        case .food: .orange
        case .groceries: .teal
        case .transport: .blue
        case .home: .purple
        case .leisure: .pink
        case .other: .gray
        }
    }
}

struct CuadraoSpendingChart: View {
    let expenses: [CanvasActivity]
    let currency: String
    let spanish: Bool
    let distribution: Bool
    let range: CanvasHistoryRange
    @Binding var periodOffset: Int
    let controls: CuadraoInsightControls
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var selectedDate: Date?
    @State private var selectedCategory: CanvasExpenseCategory?
    private var interval: DateInterval { range.interval(offset: periodOffset) }
    private var entries: [CanvasActivity] { CanvasSpendingHistory.entries(expenses, in: interval) }
    private var total: Decimal { CanvasSpendingHistory.total(entries) }
    private var buckets: [CanvasSpendingBucket] { CanvasSpendingHistory.buckets(entries, range: range) }
    private var categories: [CanvasExpenseCategory] { CanvasExpenseCategory.allCases.filter { categoryTotal($0) > 0 } }
    private var oldest: Int { CanvasSpendingHistory.oldestOffset(expenses, range: range) }
    private var unit: Calendar.Component { range == .year ? .month : .day }
    private var inspected: [CanvasActivity]? {
        guard let selectedDate, let span = Calendar.current.dateInterval(of: unit, for: selectedDate) else { return nil }
        return CanvasSpendingHistory.entries(entries, in: span)
    }
    private func categoryTotal(_ category: CanvasExpenseCategory) -> Decimal {
        CanvasSpendingHistory.total(entries.filter { $0.category == category })
    }
    private func money(_ amount: Decimal) -> String { CanvasMoney.format(amount, currency: currency) }
    private var insight: String {
        guard total > 0 else { return spanish ? "Un respiro: no hay gastos registrados aquí." : "A little breathing room: no expenses recorded here." }
        let comparison = CanvasSpendingHistory.comparisonInterval(range: range, offset: periodOffset)
        let prior = CanvasSpendingHistory.total(CanvasSpendingHistory.entries(expenses, in: comparison))
        if prior > 0, let first = expenses.first, first.date <= comparison.start {
            let difference = total - prior
            if difference == 0 { return spanish ? "Vas al mismo ritmo que en el período anterior." : "You're keeping pace with the previous period." }
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
                    Text(money(inspected.map(CanvasSpendingHistory.total) ?? total))
                        .font(CuadraoTypography.amount).lineLimit(1).minimumScaleFactor(0.5)
                        .accessibilityIdentifier("home-spending-total")
                }
                Text(selectedDate.map { $0.formatted(.dateTime.day().month(.abbreviated).year().locale(Locale(identifier: spanish ? "es_DO" : "en_US"))) } ?? (spanish ? "Gastos registrados" : "Recorded spending"))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                Text(insight).font(CuadraoTypography.supporting).fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("home-spending-insight")
            }
            controls
            if distribution { allocation } else { chart }
            if entries.isEmpty {
                Text(spanish ? "Cada movimiento que registres suma a tu historia." : "Every expense you record adds to your story.")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
            }
            ForEach(categories) { category in categoryRow(category) }
        }.onChange(of: range) { _, _ in clearSelection() }
            .onChange(of: periodOffset) { _, _ in clearSelection() }
            .onChange(of: distribution) { _, _ in clearSelection() }
            .sensoryFeedback(.selection, trigger: selectedDate)
            .sensoryFeedback(.selection, trigger: periodOffset)
    }
    private var chart: some View {
        Chart {
            ForEach(buckets) { bucket in
                BarMark(x: .value("Date", bucket.date, unit: unit), y: .value("Spending", bucket.value))
                    .foregroundStyle(by: .value("Category", bucket.category.title(spanish)))
                    .accessibilityLabel(bucket.date.formatted(date: .abbreviated, time: .omitted) + ", " + bucket.category.title(spanish))
                    .accessibilityValue(currency + " " + money(bucket.amount))
            }
            if let selectedDate {
                RuleMark(x: .value("Date", selectedDate)).foregroundStyle(WelcomePalette.ink.opacity(0.25))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 4])).accessibilityHidden(true)
            }
        }.chartForegroundStyleScale(domain: CanvasExpenseCategory.allCases.map { $0.title(spanish) }, range: CanvasExpenseCategory.allCases.map(\.color))
            .chartLegend(.hidden).chartXScale(domain: interval.start...interval.end)
            .chartYScale(domain: 0...max(1, peak * 1.15))
            .chartXAxis {
                AxisMarks(values: .stride(by: unit, count: range == .month ? 7 : range == .year ? (typeSize.isAccessibilitySize ? 3 : 2) : 1)) { value in
                    AxisTick()
                    AxisValueLabel {
                        if let date = value.as(Date.self) { Text(tick(date)).font(.caption2).fixedSize(horizontal: true, vertical: true) }
                    }
                }
            }
            .chartXAxisLabel(position: .bottom, alignment: .leading) {
                Text(axisContext).font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            .chartYAxis { AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) }
            .chartXSelection(value: $selectedDate)
            .chartGesture { proxy in
                LongPressGesture(minimumDuration: 0.2).sequenced(before: DragGesture(minimumDistance: 0))
                    .onChanged { value in
                        if case .second(true, let drag?) = value { proxy.selectXValue(at: drag.location.x) }
                    }.exclusively(before: swipe)
                    .simultaneously(with: SpatialTapGesture().onEnded { proxy.selectXValue(at: $0.location.x) })
            }
            .frame(height: 270).padding(14)
            .background(WelcomePalette.surface.opacity(0.5), in: RoundedRectangle(cornerRadius: 22))
            .overlay(alignment: .leading) { if periodOffset > oldest { edge.offset(x: -192) } }
            .overlay(alignment: .trailing) { if periodOffset < 0 { edge.offset(x: 192) } }
            .accessibilityIdentifier("home-spending-chart")
            .accessibilityValue(String(periodOffset))
            .accessibilityAction(named: Text(spanish ? "Período anterior" : "Previous period")) { move(-1) }
            .accessibilityAction(named: Text(spanish ? "Período siguiente" : "Next period")) { move(1) }
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
    private func tick(_ date: Date) -> String {
        let format = Date.FormatStyle.dateTime.locale(Locale(identifier: spanish ? "es_DO" : "en_US"))
        switch range {
        case .week: return date.formatted(format.weekday(.narrow)) + "\n" + date.formatted(format.day())
        case .month: return date.formatted(format.day())
        case .year: return date.formatted(format.month(.abbreviated))
        }
    }
    private var allocation: some View {
        VStack(alignment: .leading, spacing: 12) {
            GeometryReader { proxy in
                HStack(spacing: 0) {
                    ForEach(categories) { category in
                        Rectangle().fill(category.color)
                            .frame(width: proxy.size.width * fraction(categoryTotal(category)))
                    }
                }.clipShape(RoundedRectangle(cornerRadius: 12))
            }.frame(height: 64).accessibilityHidden(true)
            HStack {
                Text(interval.start, format: .dateTime.day().month(.abbreviated).year())
                Spacer()
                Text(interval.end.addingTimeInterval(-1), format: .dateTime.day().month(.abbreviated).year())
            }.font(CuadraoTypography.caption).foregroundStyle(.secondary)
        }.padding(.vertical, 20).contentShape(Rectangle()).gesture(swipe)
            .accessibilityIdentifier("home-spending-distribution")
            .accessibilityAction(named: Text(spanish ? "Período anterior" : "Previous period")) { move(-1) }
            .accessibilityAction(named: Text(spanish ? "Período siguiente" : "Next period")) { move(1) }
    }
    private func categoryRow(_ category: CanvasExpenseCategory) -> some View {
        DisclosureGroup(isExpanded: Binding(get: { selectedCategory == category }, set: { selectedCategory = $0 ? category : nil })) {
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
        } label: {
            HStack(spacing: 12) {
                Image(systemName: category.symbol).foregroundStyle(category.color).frame(width: 24)
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
    private var edge: some View {
        RoundedRectangle(cornerRadius: 22).fill(WelcomePalette.surface).frame(width: 180, height: 260)
            .allowsHitTesting(false).accessibilityHidden(true)
    }
    private var swipe: some Gesture {
        DragGesture(minimumDistance: 25).onEnded { value in
            guard abs(value.translation.width) > abs(value.translation.height) * 1.4 else { return }
            move(value.translation.width > 0 ? -1 : 1)
        }
    }
    private func move(_ direction: Int) { periodOffset = min(0, max(oldest, periodOffset + direction)) }
    private func clearSelection() { selectedDate = nil; selectedCategory = nil }
}
