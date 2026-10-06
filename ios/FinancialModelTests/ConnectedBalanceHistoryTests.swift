import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

final class ConnectedBalanceHistoryTests: XCTestCase {
    private let facts = HistoryFacts()

    func testPersonalShareMatchesTheServerRounding() {
        let cases: [(Int64, Int, Int64)] = [(12345, 2500, 3086), (12350, 2500, 3088), (12330, 2500, 3082), (-12350, 2500, -3088),
            (-25000, 5000, -12500), (100000, 10000, 100000), (5, 5000, 2), (15, 5000, 8), (-15, 5000, -8)]
        for (amount, bps, expected) in cases {
            XCTAssertEqual(ConnectedBalanceHistory.personalShare(amount, bps: bps), expected, "\(amount) at \(bps) bps")
        }
        XCTAssertNil(ConnectedBalanceHistory.personalShare(Int64.max, bps: 10000))
    }

    func testNoKnownAccountIsUnknown() throws {
        let summary = try facts.summary(netWorth: "0", known: 0, unknown: 1)
        XCTAssertEqual(ConnectedBalanceHistory.reading(summary: summary, reads: [], now: facts.now, calendar: facts.calendar), .unknown)
    }

    func testOneObservationTodayIsASingleDatedPoint() throws {
        let account = try facts.account(opening: facts.fact(87800, at: "2026-10-06T09:00:00-04:00", kind: "opening"))
        let summary = try facts.summary(netWorth: "87800", known: 1, unknown: 0)
        let reading = ConnectedBalanceHistory.reading(summary: summary, reads: [facts.read(account)], now: facts.now, calendar: facts.calendar)
        XCTAssertEqual(reading, .recorded(points: [CanvasBalancePoint(date: facts.day("2026-10-06"), balance: 878)], unavailableAccounts: 0))
    }

    func testTwoDatedObservationsKeepTheirRealGapAndEndOnTheHero() throws {
        let opening = facts.fact(100000, at: "2026-09-01T08:00:00-04:00", kind: "opening")
        let check = facts.fact(95000, at: "2026-09-20T23:30:00-04:00")
        let account = try facts.account(opening: opening, latest: facts.fact(87800, at: "2026-10-06T08:00:00-04:00"))
        let summary = try facts.summary(netWorth: "87800", known: 1, unknown: 0)
        let reading = ConnectedBalanceHistory.reading(summary: summary, reads: [facts.read(account, checks: [check])], now: facts.now, calendar: facts.calendar)
        XCTAssertEqual(reading, .recorded(points: [
            CanvasBalancePoint(date: facts.day("2026-09-01"), balance: 1000),
            CanvasBalancePoint(date: facts.day("2026-09-20"), balance: 950),
            CanvasBalancePoint(date: facts.day("2026-10-06"), balance: 878),
        ], unavailableAccounts: 0))
    }

    func testConfirmedZeroIsAPointAndADayWithoutObservationsIsNot() throws {
        let opening = facts.fact(5000, at: "2026-09-01T08:00:00-04:00", kind: "opening")
        let zero = facts.fact(0, at: "2026-09-20T12:00:00-04:00")
        let account = try facts.account(opening: opening, latest: zero)
        let summary = try facts.summary(netWorth: "0", known: 1, unknown: 0)
        guard case .recorded(let points, 0)? = ConnectedBalanceHistory.reading(summary: summary, reads: [facts.read(account, checks: [zero])], now: facts.now, calendar: facts.calendar) else { return XCTFail("Expected recorded history") }
        XCTAssertEqual(points.map(\.date), [facts.day("2026-09-01"), facts.day("2026-09-20"), facts.day("2026-10-06")])
        XCTAssertEqual(points.map(\.balance), [50, 0, 0])
        XCTAssertFalse(points.contains { $0.date == facts.day("2026-09-21") })
    }

    func testHeroRulesDebtSignShareArchivedAndRoundingMatchTheServer() throws {
        let checkingOpening = facts.fact(90000, at: "2026-09-01T08:00:00-04:00", kind: "opening")
        let checkingCheck = facts.fact(80000, at: "2026-09-15T12:00:00-04:00")
        let checking = try facts.account(opening: checkingOpening, latest: facts.fact(100000, at: "2026-10-06T08:00:00-04:00"), bps: 10000)
        let cardOpening = facts.fact(-20000, at: "2026-09-10T08:00:00-04:00", kind: "opening")
        let card = try facts.account(opening: cardOpening, latest: facts.fact(-25000, at: "2026-10-06T08:00:00-04:00"), type: "credit_card", bps: 5000)
        let savingsOpening = facts.fact(30000, at: "2026-09-15T18:00:00-04:00", kind: "opening")
        let savings = try facts.account(opening: savingsOpening, type: "savings", bps: 10000, archived: true)
        let propertyOpening = facts.fact(12345, at: "2026-10-06T07:00:00-04:00", kind: "opening")
        let property = try facts.account(opening: propertyOpening, type: "property", bps: 2500)
        let accounts = [checking, card, savings, property]
        XCTAssertEqual(ConnectedBalanceHistory.derivedPosition(accounts), 120586)
        let summary = try facts.summary(netWorth: "120586", known: 4, unknown: 1)
        let reads = [facts.read(checking, checks: [checkingCheck]), facts.read(card), facts.read(savings), facts.read(property)]
        let reading = ConnectedBalanceHistory.reading(summary: summary, reads: reads, now: facts.now, calendar: facts.calendar)
        XCTAssertEqual(reading, .recorded(points: [
            CanvasBalancePoint(date: facts.day("2026-09-01"), balance: 900),
            CanvasBalancePoint(date: facts.day("2026-09-10"), balance: 800),
            CanvasBalancePoint(date: facts.day("2026-09-15"), balance: 1000),
            CanvasBalancePoint(date: facts.day("2026-10-06"), balance: Decimal(string: "1205.86")!),
        ], unavailableAccounts: 0))
        guard case .recorded(let points, _)? = reading else { return XCTFail("Expected recorded history") }
        XCTAssertEqual(points.last?.balance, ConnectedBalanceHistory.amount(Decimal(string: summary.netWorthMinor)!, digits: summary.currencyFractionDigits))
    }

    func testAnotherCurrencyNeverEntersThisSeries() throws {
        let dop = try facts.account(opening: facts.fact(100000, at: "2026-09-01T08:00:00-04:00", kind: "opening"))
        let usd = try facts.account(opening: facts.fact(500, at: "2026-09-05T08:00:00-04:00", kind: "opening"), currency: "USD")
        let summary = try facts.summary(netWorth: "100000", known: 1, unknown: 0)
        let reading = ConnectedBalanceHistory.reading(summary: summary, reads: [facts.read(dop), facts.read(usd)], now: facts.now, calendar: facts.calendar)
        XCTAssertEqual(reading, .recorded(points: [
            CanvasBalancePoint(date: facts.day("2026-09-01"), balance: 1000),
            CanvasBalancePoint(date: facts.day("2026-10-06"), balance: 1000),
        ], unavailableAccounts: 0))
    }

    func testIncompleteOrUnavailableReadsAreNamedAndNeverDrawnAsComplete() throws {
        let complete = try facts.account(opening: facts.fact(60000, at: "2026-09-01T08:00:00-04:00", kind: "opening"))
        let failed = try facts.account(opening: facts.fact(40000, at: "2026-09-02T08:00:00-04:00", kind: "opening"))
        let summary = try facts.summary(netWorth: "100000", known: 2, unknown: 0)
        for read in [PersonalObservationRead.incomplete(.pageFailure), .incomplete(.pageLimit), .unavailable] {
            let reads = [facts.read(complete), ConnectedBalanceHistory.AccountRead(account: failed, read: read)]
            XCTAssertEqual(ConnectedBalanceHistory.reading(summary: summary, reads: reads, now: facts.now, calendar: facts.calendar),
                .recorded(points: [CanvasBalancePoint(date: facts.day("2026-10-06"), balance: 1000)], unavailableAccounts: 1))
        }
    }

    func testStaleOrCancelledReadsPublishNothing() throws {
        let account = try facts.account(opening: facts.fact(60000, at: "2026-09-01T08:00:00-04:00", kind: "opening"))
        let summary = try facts.summary(netWorth: "60000", known: 1, unknown: 0)
        for read in [PersonalObservationRead.stale, .cancelled] {
            XCTAssertNil(ConnectedBalanceHistory.reading(summary: summary, reads: [ConnectedBalanceHistory.AccountRead(account: account, read: read)], now: facts.now, calendar: facts.calendar))
        }
    }

    func testAccountsThatDisagreeWithTheHeroDrawOnlyTheHero() throws {
        let account = try facts.account(opening: facts.fact(60000, at: "2026-09-01T08:00:00-04:00", kind: "opening"))
        let hero = CanvasBalancePoint(date: facts.day("2026-10-06"), balance: 999)
        for (netWorth, known) in [("99900", 1), ("60000", 2)] {
            let summary = try facts.summary(netWorth: netWorth, known: known, unknown: 0)
            guard case .recorded(let points, 0)? = ConnectedBalanceHistory.reading(summary: summary, reads: [facts.read(account)], now: facts.now, calendar: facts.calendar) else { return XCTFail("Expected the hero alone") }
            XCTAssertEqual(points.map(\.date), [hero.date])
            XCTAssertEqual(points.first?.balance, ConnectedBalanceHistory.amount(Decimal(string: netWorth)!, digits: 2))
        }
    }
}

private struct HistoryFacts {
    let now = AccountPresentation.parseDate("2026-10-06T10:00:00-04:00")!
    var calendar: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/Santo_Domingo")!
        return calendar
    }
    var period: FinancialHomePeriod { .init(month: "2026-10", timeZone: "America/Santo_Domingo", startAt: "2026-10-01T00:00:00-04:00", endAtExclusive: "2026-11-01T00:00:00-04:00") }
    func day(_ value: String) -> Date {
        let parts = value.split(separator: "-").map { Int($0)! }
        return calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2]))!
    }
    func fact(_ amount: Int64, at: String, kind: String = "balance_check") -> [String: Any] {
        ["record_id": UUID().uuidString, "revision": 1, "kind": kind, "amount_minor": amount, "observed_amount_minor": amount,
         "amount": AccountPresentation.decimal(amount, digits: 2), "as_of": at, "time_zone": "America/Santo_Domingo",
         "recorded_at": "2026-10-06T12:00:00Z", "source": "manual", "revisions": []]
    }
    func account(opening: [String: Any], latest: [String: Any]? = nil, currency: String = "DOP", type: String = "checking",
                 bps: Int = 10000, archived: Bool = false) throws -> FinancialAccount {
        let latest = latest ?? opening
        let body: [String: Any] = ["id": UUID().uuidString, "type": type, "nature": type == "credit_card" ? "liability" : "asset",
            "currency": currency, "currency_fraction_digits": 2, "nickname": NSNull(), "archived": archived, "ownership_share_bps": bps,
            "version": 3, "created_at": opening["as_of"]!, "updated_at": "2026-10-06T12:00:00Z", "opening": opening,
            "balance": ["state": "known", "amount_minor": latest["amount_minor"]!, "amount": latest["amount"]!, "as_of": latest["as_of"]!, "activity_since_tracking_minor": 0],
            "asset": NSNull()]
        return try JSONDecoder().decode(FinancialAccount.self, from: JSONSerialization.data(withJSONObject: body))
    }
    func summary(netWorth: String, known: Int, unknown: Int, currency: String = "DOP") throws -> FinancialCurrencySummary {
        let body: [String: Any] = ["currency": currency, "currency_fraction_digits": 2, "cash_minor": netWorth, "other_assets_minor": "0",
            "as_of": "2026-10-06T08:00:00-04:00", "assets_minor": netWorth, "debts_minor": "0", "net_worth_minor": netWorth,
            "known_accounts": known, "unknown_accounts": unknown, "recorded_spending_minor": "0"]
        return try JSONDecoder().decode(FinancialCurrencySummary.self, from: JSONSerialization.data(withJSONObject: body))
    }
    func read(_ account: FinancialAccount, checks: [[String: Any]] = []) -> ConnectedBalanceHistory.AccountRead {
        let checks = try! JSONDecoder().decode([FinancialCheck].self, from: JSONSerialization.data(withJSONObject: checks))
        let read = PersonalAccountObservations.accepted(requestedID: account.id, before: account, checksInServerOrder: checks, after: account, period: period)
        return ConnectedBalanceHistory.AccountRead(account: account, read: read)
    }
}
