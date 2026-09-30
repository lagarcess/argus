import Foundation
import XCTest
import ArgusSession
@testable import FinancialDebtModels

@MainActor
final class FinancialDebtDraftTests: XCTestCase {
    private func debt() throws -> FinancialDebt {
        let raw = #"{"id":"\#(UUID())","version":4,"debt_account_id":"\#(UUID())","name":"Loan","currency":"DOP","currency_fraction_digits":2,"source_account_id":"\#(UUID())","amount_minor":50000,"amount":"500.00","schedule":{"cadence":"monthly","start_date":"2026-09-30","month_days":[]},"assumptions":null,"archived":false,"earliest_effective_date":"2026-11-01"}"#
        return try JSONDecoder().decode(FinancialDebt.self, from: Data(raw.utf8))
    }
    func testAmountAndFundingEditsOmitUnchangedScheduleAfterClaimedCutover() async throws {
        let existing = try debt(), nextSource = UUID()
        for (changeAmount, changeSource) in [(true, false), (false, true), (true, true)] {
            let draft = FinancialDebtDraft(debt: existing)
            if changeAmount { draft.amount = "650.00" }
            if changeSource { draft.sourceID = nextSource }
            let command = try draft.command(locale: Locale(identifier: "en_US"))
            let body = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(command)) as? [String: Any])
            XCTAssertNil(body["schedule"])
            XCTAssertEqual(body["amount"] as? String, changeAmount ? "650.00" : nil)
            XCTAssertEqual(body["source_account_id"] as? String, changeSource ? nextSource.uuidString : nil)
            XCTAssertEqual(body["effective_date"] as? String, "2026-11-01")
            XCTAssertEqual(body["expected_version"] as? Int, 4)
        }
    }
    func testExplicitScheduleEditStillSendsOnlyChangedSchedule() async throws {
        let draft = FinancialDebtDraft(debt: try debt())
        draft.start = PlanPresentation.date("2026-11-30")
        let command = try draft.command(locale: Locale(identifier: "en_US"))
        XCTAssertEqual(command.schedule?.startDate, "2026-11-30")
        XCTAssertEqual(command.schedule?.cadence, .monthly)
        XCTAssertNil(command.amount)
        XCTAssertNil(command.sourceAccountId)
        XCTAssertEqual(command.effectiveDate, "2026-11-01")
    }
    func testNameOnlyEditDoesNotCreateScheduleCutover() async throws {
        let draft = FinancialDebtDraft(debt: try debt())
        draft.name = "Renamed loan"
        let command = try draft.command(locale: Locale(identifier: "en_US"))
        XCTAssertNil(command.schedule)
        XCTAssertNil(command.amount)
        XCTAssertNil(command.sourceAccountId)
        XCTAssertNil(command.effectiveDate)
    }
}
