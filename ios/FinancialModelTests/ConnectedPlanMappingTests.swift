import Foundation
import XCTest
import ArgusSession
@testable import FinancialModels

@MainActor
final class ConnectedPlanMappingTests: XCTestCase {
    private let english = Locale(identifier: "en_US")
    private let german = Locale(identifier: "de_DE")

    func testAmountTextRoundTripsThroughTheDraftParser() throws {
        let cases: [(Double, Int, Locale, String, String)] = [
            (2500, 2, english, "2,500.00", "2500.00"),
            (1234567.891, 2, german, "1.234.567,89", "1234567.89"),
            (1235.4, 0, english, "1,235", "1235"),
            (18.5, 2, english, "18.50", "18.50"),
            (0.5, 2, german, "0,50", "0.50"),
        ]
        for (value, digits, locale, text, exact) in cases {
            let rendered = ConnectedPlanAmount.text(value, digits: digits, locale: locale)
            XCTAssertEqual(rendered, text)
            XCTAssertEqual(try AccountEntry.amount(rendered, locale: locale), exact)
            XCTAssertEqual(ConnectedPlanAmount.value(rendered, locale: locale), Double(exact))
        }
        XCTAssertEqual(ConnectedPlanAmount.text(0, digits: 2, locale: english), "")
        XCTAssertEqual(ConnectedPlanAmount.value("", locale: english), 0)
        XCTAssertEqual(ConnectedPlanAmount.value("not money", locale: english), 0)
    }

    func testGoalEditKeepsTargetDateAndScheduleTheEditorCannotShow() throws {
        let source = UUID(), destination = UUID()
        let raw = #"{"id":"\#(UUID())","version":3,"name":"Trip","currency":"DOP","currency_fraction_digits":2,"target_minor":200000,"target":"2000.00","target_date":"2027-06-30","destination_account_id":"\#(destination)","contribution_plan":{"source_account_id":"\#(source)","amount":"150.00","schedule":{"cadence":"weekly","start_date":"2026-10-09","month_days":[]}},"allocations":[],"archived":false,"earliest_effective_date":"2026-11-01"}"#
        let goal = try JSONDecoder().decode(FinancialGoal.self, from: Data(raw.utf8))
        let seeded = FinancialGoalDraft(goal: goal)
        var (plan, details) = ConnectedPlanMapping.seed(seeded, locale: .current)
        XCTAssertEqual(plan.id, goal.id)
        XCTAssertEqual(plan.kind, .goal)
        XCTAssertEqual(plan.target, 2000)
        XCTAssertEqual(plan.monthly, 150)
        XCTAssertEqual(details, .init(destinationID: destination, sourceID: source))
        plan.target = 2500; plan.name = "Longer trip"
        let draft = FinancialGoalDraft(goal: goal)
        ConnectedPlanMapping.apply(plan, details, to: draft, digits: 2, locale: english)
        XCTAssertTrue(draft.ready)
        let command = try draft.command(locale: english)
        XCTAssertEqual(command.name, "Longer trip")
        XCTAssertEqual(command.target, "2500.00")
        XCTAssertNil(command.currency)
        XCTAssertEqual(command.targetDate, "2027-06-30")
        XCTAssertEqual(command.destinationAccountId, destination)
        XCTAssertEqual(command.contributionPlan?.sourceAccountId, source)
        XCTAssertEqual(command.contributionPlan?.amount, "150.00")
        XCTAssertEqual(command.contributionPlan?.schedule.cadence, .weekly)
        XCTAssertEqual(command.contributionPlan?.schedule.startDate, "2026-10-09")
        XCTAssertEqual(command.expectedVersion, 3)
    }

    func testGoalContributionNeedsAFundingAccountBeforeItIsReady() throws {
        var plan = CanvasPlan(name: "Fund", kind: .goal, currency: "DOP")
        plan.target = 1000; plan.monthly = 100
        let destination = UUID()
        let draft = FinancialGoalDraft(start: "2026-10-06", currency: "USD")
        ConnectedPlanMapping.apply(plan, .init(destinationID: destination), to: draft, digits: 2, locale: english)
        XCTAssertEqual(draft.currency, "DOP")
        XCTAssertTrue(draft.hasPlan)
        XCTAssertFalse(draft.ready)
        ConnectedPlanMapping.apply(plan, .init(destinationID: destination, sourceID: UUID()), to: draft, digits: 2, locale: english)
        XCTAssertTrue(draft.ready)
        plan.monthly = 0
        ConnectedPlanMapping.apply(plan, .init(destinationID: destination), to: draft, digits: 2, locale: english)
        XCTAssertFalse(draft.hasPlan)
        XCTAssertNil(try draft.command(locale: english).contributionPlan)
    }

    func testBudgetEditKeepsItsMonth() throws {
        let account = UUID()
        let raw = #"{"id":"\#(UUID())","version":2,"name":"Food","limit_minor":15000,"limit":"150.00","currency":"DOP","currency_fraction_digits":2,"month":"2026-10","account_ids":["\#(account)"],"category_ids":["groceries"],"include_uncategorized":false,"archived":false}"#
        let budget = try JSONDecoder().decode(FinancialBudget.self, from: Data(raw.utf8))
        var (plan, details) = ConnectedPlanMapping.seed(FinancialBudgetDraft(budget: budget), locale: .current)
        XCTAssertEqual(plan.target, 150)
        XCTAssertEqual(plan.monthly, 150)
        XCTAssertEqual(details, .init(accountIDs: [account], categoryIDs: ["groceries"]))
        plan.target = 160; details.includeUncategorized = true
        let draft = FinancialBudgetDraft(budget: budget)
        ConnectedPlanMapping.apply(plan, details, to: draft, digits: 2, locale: german)
        let command = try draft.command(locale: german)
        XCTAssertEqual(command.limit, "160.00")
        XCTAssertEqual(command.month, "2026-10")
        XCTAssertEqual(command.currency, "DOP")
        XCTAssertEqual(command.accountIds, [account])
        XCTAssertEqual(command.categoryIds, ["groceries"])
        XCTAssertTrue(command.includeUncategorized)
        XCTAssertEqual(command.expectedVersion, 2)
    }

    func testDebtEditKeepsFeesAndScheduleWhenOnlyTheRateMoves() throws {
        let source = UUID()
        let raw = #"{"id":"\#(UUID())","version":4,"debt_account_id":"\#(UUID())","name":"Loan","currency":"DOP","currency_fraction_digits":2,"source_account_id":"\#(source)","amount_minor":50000,"amount":"500.00","schedule":{"cadence":"twice_monthly","start_date":"2026-09-30","month_days":[15,31]},"assumptions":{"annual_rate_percent":"18.00","recurring_fees":"25.00","first_period_start":"2026-09-01","no_new_borrowing":true},"archived":false,"earliest_effective_date":"2026-11-01"}"#
        let debt = try JSONDecoder().decode(FinancialDebt.self, from: Data(raw.utf8))
        var (plan, details) = ConnectedPlanMapping.seed(FinancialDebtDraft(debt: debt), locale: .current)
        XCTAssertEqual(plan.monthly, 500)
        XCTAssertEqual(plan.annualRate, 18)
        XCTAssertEqual(details.sourceID, source)
        XCTAssertEqual(details.debtAccountID, debt.debtAccountId)
        plan.annualRate = 20.5
        let draft = FinancialDebtDraft(debt: debt)
        ConnectedPlanMapping.apply(plan, details, to: draft, digits: 2, locale: english)
        let command = try draft.command(locale: english)
        XCTAssertNil(command.amount)
        XCTAssertNil(command.sourceAccountId)
        XCTAssertNil(command.schedule)
        XCTAssertNil(command.effectiveDate)
        XCTAssertEqual(command.assumptions?.annualRatePercent, "20.50")
        XCTAssertEqual(command.assumptions?.recurringFees, "25.00")
        XCTAssertEqual(command.assumptions?.firstPeriodStart, "2026-09-01")
        plan.annualRate = 0
        ConnectedPlanMapping.apply(plan, details, to: draft, digits: 2, locale: english)
        XCTAssertNil(try draft.command(locale: english).assumptions)
    }

    func testNewDebtEstimateStartsWithoutFees() throws {
        let raw = #"{"id":"\#(UUID())","type":"credit_card","nature":"liability","currency":"USD","currency_fraction_digits":2,"nickname":"Visa","archived":false,"ownership_share_bps":10000,"version":1,"created_at":"2026-09-01T12:00:00Z","updated_at":"2026-09-01T12:00:00Z","balance":{"state":"known","amount_minor":-40000,"amount":"-400.00","as_of":"2026-10-01","activity_since_tracking_minor":0}}"#
        let account = try JSONDecoder().decode(FinancialAccount.self, from: Data(raw.utf8))
        let draft = FinancialDebtDraft(account: account, start: "2026-10-06")
        var plan = CanvasPlan(name: "", kind: .debt, currency: "USD")
        plan.monthly = 120; plan.annualRate = 12
        ConnectedPlanMapping.apply(plan, .init(sourceID: UUID(), debtAccountID: account.id), to: draft, digits: 2, locale: english)
        XCTAssertEqual(draft.name, "")
        XCTAssertFalse(draft.ready)
        plan.name = "Visa payoff"
        ConnectedPlanMapping.apply(plan, .init(sourceID: UUID(), debtAccountID: account.id), to: draft, digits: 2, locale: english)
        let command = try draft.command(locale: english)
        XCTAssertEqual(command.debtAccountId, account.id)
        XCTAssertEqual(command.amount, "120.00")
        XCTAssertEqual(command.schedule?.cadence, .monthly)
        XCTAssertEqual(command.schedule?.startDate, "2026-10-06")
        XCTAssertEqual(command.assumptions?.annualRatePercent, "12.00")
        XCTAssertEqual(command.assumptions?.recurringFees, "0")
        XCTAssertEqual(command.assumptions?.firstPeriodStart, "2026-10-06")
    }
}
