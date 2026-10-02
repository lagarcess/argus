import Foundation

struct CanvasBalanceChange: Identifiable {
    let account: CanvasAccount
    let opening: Decimal?
    let closing: Decimal?
    var id: UUID { account.id }
    var change: Decimal? {
        guard let opening, let closing else { return nil }
        return closing - opening
    }
}

/// One pair of observed snapshots owns the amount, allocation and account changes.
struct CanvasBalancePeriod {
    let interval: DateInterval
    let opening: CanvasBalancePoint?
    let closing: CanvasBalancePoint?
    let closingAccounts: [CanvasAccount]
    let changes: [CanvasBalanceChange]
    let isPartial: Bool
    var change: Decimal? {
        guard let opening, let closing else { return nil }
        return closing.balance - opening.balance
    }

    init(accounts: [CanvasAccount], observations: [CanvasBalanceObservation], range: CanvasHistoryRange,
         offset: Int, now: Date = .now) {
        let window = range.interval(now: now, offset: offset)
        interval = window
        let history = CanvasBalanceHistory.points(accounts: accounts, observations: observations, now: now)
        closing = history.last { $0.date < window.end && $0.date <= now }
        if let closing, closing.date >= window.start {
            opening = history.last { $0.date <= window.start && $0.date < closing.date }
                ?? history.first { $0.date >= window.start && $0.date < closing.date }
        } else { opening = nil }
        let today = Calendar.current.startOfDay(for: now)
        func snapshot(_ point: CanvasBalancePoint?) -> [CanvasAccount] {
            guard let point else { return accounts.map { account in var copy = account; copy.balance = nil; return copy } }
            return point.date == today ? accounts : CanvasBalanceHistory.snapshot(accounts: accounts, observations: observations, at: point.date)
        }
        closingAccounts = snapshot(closing)
        let starting = snapshot(opening)
        changes = zip(starting, closingAccounts).map { start, end in
            CanvasBalanceChange(account: end,
                opening: start.balance.map { CanvasBalanceHistory.contribution($0, account: start) },
                closing: end.balance.map { CanvasBalanceHistory.contribution($0, account: end) })
        }
        isPartial = closingAccounts.contains { $0.balance == nil }
    }
}
