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
    var symbol: String {
        switch self { case .food: "fork.knife"; case .groceries: "basket"; case .transport: "tram"; case .home: "house"; case .leisure: "sparkles"; case .other: "ellipsis" }
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
        let component: Calendar.Component = range == .year ? .month : .day
        let grouped = Dictionary(grouping: entries) { Calendar.current.dateInterval(of: component, for: $0.date)!.start }
        return grouped.keys.sorted().flatMap { date in
            CanvasExpenseCategory.allCases.compactMap { category in
                let amount = total(grouped[date]!.filter { $0.category == category })
                return amount > 0 ? CanvasSpendingBucket(date: date, category: category, amount: amount) : nil
            }
        }
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
        let today = calendar.startOfDay(for: now)
        let categories: [CanvasExpenseCategory] = [.food, .groceries, .transport, .home, .leisure]
        return accounts.filter { $0.kind == .checking || $0.kind == .cash }.enumerated().flatMap { index, account in
            stride(from: 1, through: 270, by: 3).map { day in
                let category = categories[(day / 3 + index) % categories.count]
                let amount = Decimal([650, 2450, 320, 1800, 900][categories.firstIndex(of: category)!] + (day % 7) * 40)
                return CanvasActivity(accountID: account.id, title: category.title(spanish), amount: amount,
                    date: calendar.date(byAdding: .day, value: -day, to: today)!, income: false, category: category)
            }
        }
    }
}
