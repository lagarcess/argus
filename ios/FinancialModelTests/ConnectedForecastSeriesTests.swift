import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

final class ConnectedForecastSeriesTests: XCTestCase {
    func testScheduledItemsStepOnTheirDatesAndHoldToTheWindowEnd() throws {
        let currency = try forecast(points: [point("2026-10-06", "87800"), point("2026-10-15", "67800", occurrence: "rent"), point("2026-10-25", "127800", occurrence: "salary")])
        XCTAssertEqual(ConnectedForecastSeries.reading(currency, end: "2026-11-05"), .series([
            .init(date: "2026-10-06", balanceMinor: "87800"), .init(date: "2026-10-15", balanceMinor: "67800"),
            .init(date: "2026-10-25", balanceMinor: "127800"), .init(date: "2026-11-05", balanceMinor: "127800"),
        ], scheduled: true))
    }

    func testNothingScheduledIsAFlatLineFlaggedAsSuch() throws {
        let currency = try forecast(points: [point("2026-10-06", "87800")])
        XCTAssertEqual(ConnectedForecastSeries.reading(currency, end: "2026-11-05"),
            .series([.init(date: "2026-10-06", balanceMinor: "87800"), .init(date: "2026-11-05", balanceMinor: "87800")], scheduled: false))
    }

    func testAnOccurrenceOnTheLastDayIsNotRepeated() throws {
        let currency = try forecast(points: [point("2026-10-06", "87800"), point("2026-11-05", "67800", occurrence: "rent")])
        XCTAssertEqual(ConnectedForecastSeries.reading(currency, end: "2026-11-05"),
            .series([.init(date: "2026-10-06", balanceMinor: "87800"), .init(date: "2026-11-05", balanceMinor: "67800")], scheduled: true))
    }

    func testUnknownStartingBalanceHasNoSeries() throws {
        XCTAssertEqual(ConnectedForecastSeries.reading(try forecast(points: [point("2026-10-06", nil)]), end: "2026-11-05"), .unknown)
        XCTAssertEqual(ConnectedForecastSeries.reading(try forecast(points: [point("2026-10-06", "87800")], unknown: [UUID()]), end: "2026-11-05"), .unknown)
        XCTAssertEqual(ConnectedForecastSeries.reading(try forecast(points: []), end: "2026-11-05"), .unknown)
    }

    private func point(_ date: String, _ balance: String?, occurrence: String? = nil) -> [String: Any] {
        ["date": date, "occurrence_id": occurrence as Any? ?? NSNull(), "change_minor": "0", "known_balance_minor": balance ?? "0", "balance_minor": balance as Any? ?? NSNull()]
    }
    private func forecast(points: [[String: Any]], unknown: [UUID] = []) throws -> FinancialForecastCurrency {
        let body: [String: Any] = ["currency": "DOP", "currency_fraction_digits": 2, "account_ids": [UUID().uuidString] + unknown.map(\.uuidString),
            "unknown_account_ids": unknown.map(\.uuidString), "known_starting_minor": "87800", "starting_minor": unknown.isEmpty ? "87800" : NSNull(),
            "expected_income_minor": "0", "expected_bills_minor": "0", "transfer_effect_minor": NSNull(), "net_cash_change_minor": "0",
            "ending_minor": (points.last?["balance_minor"] as? String) as Any? ?? NSNull(), "first_shortfall_date": NSNull(), "as_of": NSNull(), "points": points, "order": "bills_before_income"]
        return try JSONDecoder().decode(FinancialForecastCurrency.self, from: JSONSerialization.data(withJSONObject: body))
    }
}
