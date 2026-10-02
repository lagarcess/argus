import Foundation

enum CanvasExpenseCategory: String, CaseIterable, Identifiable {
    case food, groceries, transport, home, leisure, other
    var id: String { rawValue }
    func title(_ es: Bool) -> String {
        switch self {
        case .food: es ? "Comida" : "Food"
        case .groceries: es ? "Supermercado" : "Groceries"
        case .transport: es ? "Transporte" : "Transport"
        case .home: es ? "Casa" : "Home"
        case .leisure: es ? "Disfrutar" : "Leisure"
        case .other: es ? "Otros" : "Other"
        }
    }

}

struct CanvasSpendingBucket: Identifiable {
    let date: Date
    let category: CanvasExpenseCategory
    let amount: Decimal
    var id: String { "\(date.timeIntervalSince1970)-\(category.rawValue)" }
    var value: Double { NSDecimalNumber(decimal: amount).doubleValue }
}

/// Expenses come from the same local activity owner as the rows, never balance deltas.
enum CanvasSpendingHistory {
    static func expenses(_ activity: [CanvasActivity], accounts: [CanvasAccount], currency: String, now: Date = .now) -> [CanvasActivity] {
        let ids = Set(accounts.filter { $0.currency == currency }.map(\.id))
        return activity.filter { ids.contains($0.accountID) && !$0.income && $0.amount > 0 && $0.date <= now }.sorted { $0.date < $1.date }
    }
    static func entries(_ expenses: [CanvasActivity], in interval: DateInterval) -> [CanvasActivity] {
        expenses.filter { $0.date >= interval.start && $0.date < interval.end }
    }
    static func total(_ entries: [CanvasActivity]) -> Decimal { entries.reduce(0) { $0 + $1.amount } }
    static func buckets(_ entries: [CanvasActivity], range: CanvasHistoryRange) -> [CanvasSpendingBucket] {
        let grouped = Dictionary(grouping: entries) { bucketInterval(containing: $0.date, range: range).start }
        return grouped.keys.sorted().flatMap { date in
            CanvasExpenseCategory.allCases.compactMap { category in
                let amount = total(grouped[date]!.filter { $0.category == category })
                return amount > 0 ? CanvasSpendingBucket(date: date, category: category, amount: amount) : nil
            }
        }
    }
    static func bucketInterval(containing date: Date, range: CanvasHistoryRange, calendar: Calendar = .current) -> DateInterval {
        let component: Calendar.Component = range == .year ? .month : range == .month ? .weekOfYear : .day
        let bucket = calendar.dateInterval(of: component, for: date)!
        guard range == .month else { return bucket }
        let month = calendar.dateInterval(of: .month, for: date)!
        return DateInterval(start: max(bucket.start, month.start), end: min(bucket.end, month.end))
    }
    static func slots(in interval: DateInterval, range: CanvasHistoryRange) -> [DateInterval] {
        var result: [DateInterval] = []
        var date = interval.start
        while date < interval.end {
            let span = bucketInterval(containing: date, range: range)
            result.append(span)
            date = span.end
        }
        return result
    }
    static func oldestOffset(_ expenses: [CanvasActivity], range: CanvasHistoryRange, now: Date = .now) -> Int {
        range.oldestOffset(expenses.map { CanvasBalancePoint(date: $0.date, balance: 0) }, now: now)
    }
    /// For the running period, compare the same elapsed span, not a partial month with a full one.
    static func comparisonInterval(range: CanvasHistoryRange, offset: Int, now: Date = .now) -> DateInterval {
        let current = range.interval(now: now, offset: offset)
        let previous = range.interval(now: now, offset: offset - 1)
        guard offset == 0 else { return previous }
        let elapsed = Calendar.current.dateComponents([.day, .hour, .minute, .second], from: current.start, to: now)
        let end = min(previous.end, Calendar.current.date(byAdding: elapsed, to: previous.start)!)
        return DateInterval(start: previous.start, end: max(previous.start, end))
    }
    static func examples(accounts: [CanvasAccount], spanish: Bool, now: Date) -> [CanvasActivity] {
        let calendar = Calendar.current
        let days = CanvasPreviewHistory.days(now: now)
        return accounts.filter { $0.kind == .checking || $0.kind == .cash }.enumerated().flatMap { index, account in
            days.compactMap { date in
                let seed = CanvasPreviewHistory.variation(date, salt: index)
                let day = calendar.component(.day, from: date)
                let month = calendar.component(.month, from: date)
                var category: CanvasExpenseCategory
                var amount: Int
                var title: String
                if account.sharedWithHousehold && day == 5 {
                    category = .home; amount = 4800; title = spanish ? "Servicios del hogar" : "Household bills"
                } else if account.sharedWithHousehold && seed % 11 == 0 {
                    category = .groceries; amount = 1700 + seed % 1400; title = spanish ? "Compra de la semana" : "Weekly groceries"
                } else if account.kind == .checking && !account.sharedWithHousehold && day == 2 {
                    category = .home; amount = 12500; title = spanish ? "Alquiler" : "Rent"
                } else if account.kind == .checking && day == 19 && [3, 7, 12].contains(month) {
                    category = .leisure; amount = 3200 + seed % 5800; title = spanish ? "Escapada" : "Weekend away"
                } else if account.kind == .cash && seed % 5 == 0 {
                    category = .food; amount = 95 + seed % 180; title = spanish ? "Café y algo más" : "Coffee and a bite"
                } else if account.kind == .checking && seed % 9 == 0 {
                    category = .food; amount = 600 + seed % 1900 + (calendar.dateComponents([.month], from: days.first!, to: date).month ?? 0) * 75; title = spanish ? "Comida fuera" : "Eating out"
                } else if account.kind == .checking && seed % 13 == 0 {
                    category = .transport; amount = 180 + seed % 750; title = spanish ? "Transporte" : "Getting around"
                } else { return nil }
                return CanvasActivity(accountID: account.id, title: title, amount: Decimal(amount),
                    date: date, income: false, category: category)
            }
        }
    }
}
