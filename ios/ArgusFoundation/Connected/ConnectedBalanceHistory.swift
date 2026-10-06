import Foundation
import ArgusSession

/// Recorded positions of one currency, totalled the way the server hero totals them: every owner account,
/// archived included, the owner-signed amount and the account's current ownership share rounded half to even.
/// Today's point is the hero itself. Dated points exist only on days an account recorded a balance.
enum ConnectedBalanceHistory {
    struct AccountRead: Equatable {
        let account: FinancialAccount
        let read: PersonalObservationRead
    }

    enum Reading: Equatable {
        /// No account in this currency has a known balance.
        case unknown
        /// Dated positions ending on the hero today. Accounts whose history could not be read are counted,
        /// and while any is missing only the hero point is drawn.
        case recorded(points: [CanvasBalancePoint], unavailableAccounts: Int)
    }

    /// Mirrors the server's `personal_share`: scale by basis points, round half to even, keep the sign.
    static func personalShare(_ amount: Int64, bps: Int) -> Int64? {
        guard bps >= 0 else { return nil }
        let (scaled, overflow) = amount.magnitude.multipliedReportingOverflow(by: UInt64(bps))
        guard !overflow else { return nil }
        var quotient = scaled / 10000
        let remainder = scaled % 10000
        if remainder > 5000 || (remainder == 5000 && quotient % 2 == 1) { quotient += 1 }
        guard quotient <= UInt64(Int64.max) else { return nil }
        return amount >= 0 ? Int64(quotient) : -Int64(quotient)
    }

    /// The hero recomputed from the listed accounts; nil when a share or the total overflows.
    static func derivedPosition(_ accounts: [FinancialAccount]) -> Int64? {
        var total: Int64 = 0
        for account in accounts {
            guard let amount = account.balance.amountMinor,
                  let share = personalShare(amount, bps: account.ownershipShareBps) else { return nil }
            let (sum, overflow) = total.addingReportingOverflow(share)
            guard !overflow else { return nil }
            total = sum
        }
        return total
    }

    static func amount(_ minor: Decimal, digits: Int) -> Decimal {
        Decimal(sign: minor < 0 ? .minus : .plus, exponent: -digits, significand: abs(minor))
    }

    /// `reads` covers every account with a known balance; other currencies are ignored here.
    /// Returns nil when a read belongs to another identity or was cancelled: nothing of it may be shown.
    static func reading(summary: FinancialCurrencySummary, reads: [AccountRead], now: Date,
                        calendar: Calendar = .current) -> Reading? {
        guard summary.knownAccounts > 0, let hero = Decimal(string: summary.netWorthMinor) else { return .unknown }
        let reads = reads.filter { $0.account.currency == summary.currency }
        let today = calendar.startOfDay(for: now)
        let heroPoint = CanvasBalancePoint(date: today, balance: amount(hero, digits: summary.currencyFractionDigits))
        var complete: [(account: FinancialAccount, facts: PersonalAccountObservations)] = []
        var unavailable = 0
        for entry in reads {
            switch entry.read {
            case .stale, .cancelled: return nil
            case .incomplete, .unavailable: unavailable += 1
            case .complete(let facts): complete.append((entry.account, facts))
            }
        }
        guard unavailable == 0 else { return .recorded(points: [heroPoint], unavailableAccounts: unavailable) }
        let listed = reads.map(\.account)
        let consistent = Int64(summary.netWorthMinor) == derivedPosition(listed)
            && listed.count == summary.knownAccounts
            && complete.allSatisfy { $0.facts.accountVersion == $0.account.version }
        guard consistent else { return .recorded(points: [heroPoint], unavailableAccounts: 0) }
        // Per account, the last balance recorded on each day, keyed by that day's local midnight.
        let recorded: [(bps: Int, byDay: [Date: Int64])] = complete.map { account, facts in
            var byDay: [Date: Int64] = [:]
            for observation in facts.observations {
                var zoned = calendar
                zoned.timeZone = TimeZone(identifier: observation.timeZone) ?? calendar.timeZone
                let parts = zoned.dateComponents([.year, .month, .day], from: observation.instant)
                guard let day = calendar.date(from: parts), day < today else { continue }
                byDay[day] = observation.amountMinor
            }
            return (account.ownershipShareBps, byDay)
        }
        let days = Set(recorded.flatMap { $0.byDay.keys }).sorted()
        var points: [CanvasBalancePoint] = []
        for day in days {
            var total: Int64 = 0
            for (bps, byDay) in recorded {
                guard let latest = byDay.filter({ $0.key <= day }).max(by: { $0.key < $1.key }) else { continue }
                guard let share = personalShare(latest.value, bps: bps) else { return .recorded(points: [heroPoint], unavailableAccounts: 0) }
                let (sum, overflow) = total.addingReportingOverflow(share)
                guard !overflow else { return .recorded(points: [heroPoint], unavailableAccounts: 0) }
                total = sum
            }
            points.append(CanvasBalancePoint(date: day, balance: amount(Decimal(total), digits: summary.currencyFractionDigits)))
        }
        points.append(heroPoint)
        return .recorded(points: points, unavailableAccounts: 0)
    }
}
