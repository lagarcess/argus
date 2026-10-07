import Foundation
import ArgusSession

/// The server's schedule-based projection drawn across the whole window. Each server point is the balance after
/// that date's scheduled items; the window end repeats the last balance because nothing else is scheduled.
enum ConnectedForecastSeries: Equatable {
    struct Point: Equatable {
        let date: String
        let balanceMinor: String
    }
    /// A starting balance is missing, so there is nothing to project.
    case unknown
    /// `scheduled` is false when no bill or income falls inside the window: the line is flat, not a prediction.
    case series([Point], scheduled: Bool)

    static func reading(_ currency: FinancialForecastCurrency, end: String) -> ConnectedForecastSeries {
        guard currency.unknownAccountIds.isEmpty, !currency.points.isEmpty else { return .unknown }
        var points: [Point] = []
        for point in currency.points {
            guard let balance = point.balanceMinor else { return .unknown }
            points.append(Point(date: point.date, balanceMinor: balance))
        }
        if let last = points.last, last.date < end { points.append(Point(date: end, balanceMinor: last.balanceMinor)) }
        return .series(points, scheduled: currency.points.contains { $0.occurrenceId != nil })
    }
}

/// Why Plan shows its cold start instead of a forecast. Nil once any included account has a known balance.
enum ConnectedForecastStart: Equatable {
    case noAccounts
    case noAccountsIncluded
    case noKnownBalance

    static func reading(_ currencies: [FinancialForecastCurrency], hasAccounts: Bool) -> ConnectedForecastStart? {
        guard hasAccounts else { return .noAccounts }
        guard !currencies.isEmpty else { return .noAccountsIncluded }
        let known = currencies.contains { currency in currency.accountIds.contains { !currency.unknownAccountIds.contains($0) } }
        return known ? nil : .noKnownBalance
    }
}
