import Foundation

/// Recorded-position projection for the UI preview, never a spendable-cash forecast.
struct CanvasBalanceObservation {
    let accountID: UUID
    let currency: String
    let kind: CanvasAccountKind
    let share: Int
    let date: Date
    let balance: Decimal
}

struct CanvasBalancePoint: Identifiable, Equatable {
    let date: Date
    let balance: Decimal
    var id: Date { date }
    var value: Double { NSDecimalNumber(decimal: balance).doubleValue }
}

enum CanvasBalanceHistory {
    static func position(_ accounts: [CanvasAccount]) -> Decimal? {
        let known = accounts.filter { $0.balance != nil }
        guard !known.isEmpty else { return nil }
        return known.reduce(Decimal.zero) { $0 + contribution($1.balance!, account: $1) }
    }

    static func points(accounts: [CanvasAccount], observations: [CanvasBalanceObservation], now: Date) -> [CanvasBalancePoint] {
        guard let current = position(accounts) else { return [] }
        let known = accounts.filter { $0.balance != nil }
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: now)
        // Never invent earlier balances for a new account or reinterpret another currency/share.
        let matched = known.map { account in
            observations.filter {
                $0.accountID == account.id && $0.currency == account.currency && $0.kind == account.kind
                    && $0.share == account.share && $0.date < today
            }
        }
        let dates = Set(matched.flatMap { $0.map(\.date) }).sorted()
        var result: [CanvasBalancePoint] = []
        for date in dates {
            let values = matched.map { rows in rows.first { $0.date == date }?.balance }
            guard values.allSatisfy({ $0 != nil }) else { continue }
            let total = zip(known, values).reduce(Decimal.zero) { $0 + contribution($1.1!, account: $1.0) }
            result.append(CanvasBalancePoint(date: date, balance: total))
        }
        result.append(CanvasBalancePoint(date: today, balance: current))
        return result
    }

    static func contribution(_ balance: Decimal, account: CanvasAccount) -> Decimal {
        balance * (account.kind.isDebt ? -1 : 1) * Decimal(account.kind.isAsset ? account.share : 100) / 100
    }

    /// Explicit example observations, separate from activity and never backfilled for created accounts.
    static func examples(accounts: [CanvasAccount], now: Date) -> [CanvasBalanceObservation] {
        let days = [-29, -25, -21, -18, -14, -10, -7, -3]
        let changes: [[Int]] = [
            [-8200, -6100, -6900, -4200, -5400, -2900, -3400, -1200],
            [800, 620, 440, 600, 300, 180, 420, 180],
            [-5000, -5000, -5000, -2500, -2500, -2500, 0, 0],
            [4200, 3600, 3100, 5500, 2900, 1900, 2700, 900],
            [-2500, -2500, -2500, -2500, 0, 0, 0, 0]
        ]
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: now)
        return accounts.enumerated().flatMap { index, account in
            guard let balance = account.balance, index < changes.count else { return [CanvasBalanceObservation]() }
            let older = (-9 ... -1).flatMap { month in
                let anchor = calendar.date(byAdding: .month, value: month, to: today)!
                let start = calendar.dateInterval(of: .month, for: anchor)!.start
                return (0..<4).map { week in
                    CanvasBalanceObservation(accountID: account.id, currency: account.currency, kind: account.kind,
                        share: account.share, date: calendar.date(byAdding: .day, value: week * 7, to: start)!,
                        balance: balance * Decimal(100 + month * 4 + week) / 100)
                }
            }
            return older.filter { $0.date < calendar.date(byAdding: .day, value: -29, to: today)! } + zip(days, changes[index]).map { day, change in
                CanvasBalanceObservation(accountID: account.id, currency: account.currency, kind: account.kind,
                    share: account.share, date: calendar.date(byAdding: .day, value: day, to: today)!, balance: balance + Decimal(change))
            }
        }
    }
}

/// Calendar periods own filtering, paging bounds and the balance comparison.
enum CanvasHistoryRange: String, CaseIterable, Identifiable {
    case week, month, year
    var id: String { rawValue }
    var component: Calendar.Component {
        switch self { case .week: .weekOfYear; case .month: .month; case .year: .year }
    }
    func title(_ es: Bool) -> String {
        switch self {
        case .week: es ? "Semana" : "Week"
        case .month: es ? "Mes" : "Month"
        case .year: es ? "Año" : "Year"
        }
    }
    func interval(now: Date = .now, offset: Int = 0) -> DateInterval {
        let calendar = Calendar.current
        let current = calendar.dateInterval(of: component, for: now)!.start
        return calendar.dateInterval(of: component, for: calendar.date(byAdding: component, value: min(offset, 0), to: current)!)!
    }
    func points(_ points: [CanvasBalancePoint], now: Date = .now, offset: Int = 0) -> [CanvasBalancePoint] {
        let window = interval(now: now, offset: offset)
        return points.filter { $0.date >= window.start && $0.date < window.end && $0.date <= now }
    }
    func oldestOffset(_ points: [CanvasBalancePoint], now: Date = .now) -> Int {
        guard let first = points.first else { return 0 }
        let start = Calendar.current.dateInterval(of: component, for: first.date)!.start
        return min(0, Calendar.current.dateComponents([component], from: interval(now: now).start, to: start).value(for: component) ?? 0)
    }
    func baseline(_ history: [CanvasBalancePoint], now: Date = .now, offset: Int = 0) -> CanvasBalancePoint? {
        let start = interval(now: now, offset: offset).start
        return history.last { $0.date < start } ?? points(history, now: now, offset: offset).first
    }
}

/// Quiet Home offers only windows covered by recorded history.
enum CanvasHomeRange: String, CaseIterable, Identifiable {
    case month, twoMonths, quarter, halfYear, year, all
    var id: String { rawValue }
    var months: Int? {
        switch self {
        case .month: 1; case .twoMonths: 2; case .quarter: 3
        case .halfYear: 6; case .year: 12; case .all: nil
        }
    }
    func title(_ es: Bool) -> String {
        guard let months else { return es ? "Todo" : "All" }
        if months == 12 { return es ? "1 año" : "1Y" }
        return es ? "\(months) \(months == 1 ? "mes" : "meses")" : "\(months)M"
    }
    func start(now: Date) -> Date? {
        months.map { Calendar.current.date(byAdding: .month, value: -$0, to: Calendar.current.startOfDay(for: now))! }
    }
    static func available(_ points: [CanvasBalancePoint], now: Date = .now) -> [Self] {
        guard let first = points.first, points.count > 1 else { return [.all] }
        return allCases.filter { option in option.start(now: now).map { first.date <= $0 } ?? true }
    }
    func points(_ points: [CanvasBalancePoint], now: Date = .now) -> [CanvasBalancePoint] {
        guard let start = start(now: now) else { return points }
        return points.filter { $0.date >= start && $0.date <= now }
    }
}
