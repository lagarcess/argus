import Foundation

/// One period owns the hero, takeaway, highlights and their supporting records.
struct CanvasSpendingStory {
    let expenses: [CanvasActivity]
    let range: CanvasHistoryRange
    let offset: Int
    let coverageStart: Date?
    var now: Date = .now
    var interval: DateInterval { range.interval(now: now, offset: offset) }
    var entries: [CanvasActivity] {
        CanvasSpendingHistory.entries(expenses.filter { $0.date <= now }, in: interval)
    }
    var total: Decimal { CanvasSpendingHistory.total(entries) }
    var covered: Bool { coverageStart.map { $0 <= interval.start } ?? false }
    var comparison: DateInterval? {
        let prior = CanvasSpendingHistory.comparisonInterval(range: range, offset: offset, now: now)
        guard covered, let coverageStart, coverageStart <= prior.start else { return nil }
        // The 31st of a month has no equivalent point in a 30-day previous month.
        if offset == 0 {
            let calendar = Calendar.current
            let elapsed = calendar.dateComponents([.day, .hour, .minute, .second], from: interval.start, to: now)
            let priorElapsed = calendar.dateComponents([.day, .hour, .minute, .second], from: prior.start, to: prior.end)
            guard elapsed == priorElapsed else { return nil }
        }
        return prior
    }
    var previousEntries: [CanvasActivity]? {
        comparison.map { CanvasSpendingHistory.entries(expenses, in: $0) }
    }
    var previousTotal: Decimal? { previousEntries.map(CanvasSpendingHistory.total) }
    func total(for category: CanvasExpenseCategory, previous: Bool = false) -> Decimal {
        CanvasSpendingHistory.total((previous ? previousEntries ?? [] : entries).filter { $0.category == category })
    }
    var changedCategory: CanvasExpenseCategory? {
        guard previousEntries != nil, total > 0 else { return nil }
        return CanvasExpenseCategory.allCases.filter { total(for: $0) != total(for: $0, previous: true) }
            .max { abs(total(for: $0) - total(for: $0, previous: true)) < abs(total(for: $1) - total(for: $1, previous: true)) }
    }
    var largestExpense: CanvasActivity? {
        guard entries.count > 1 else { return nil }
        return entries.max { $0.amount < $1.amount }
    }
    func periodText(_ interval: DateInterval, spanish: Bool) -> String {
        let style = Date.FormatStyle.dateTime.locale(Locale(identifier: spanish ? "es_DO" : "en_US"))
        if range == .year && offset < 0 { return interval.start.formatted(style.year()) }
        let end = max(interval.start, interval.end.addingTimeInterval(-1))
        return interval.start.formatted(style.month(.abbreviated).day()) + " – " + end.formatted(style.month(.abbreviated).day())
    }
    var observedInterval: DateInterval { DateInterval(start: interval.start, end: min(interval.end, max(interval.start, now))) }
}
