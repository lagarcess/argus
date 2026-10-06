import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

final class PlanScenarioTests: XCTestCase {
    private func decode<T: Decodable>(_ type: T.Type, _ raw: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(raw.utf8))
    }
    private func instant(_ raw: String) throws -> Date { try XCTUnwrap(AccountPresentation.parseDate(raw)) }

    private func budget(limitMinor: Int64 = 2500000, spentMinor: String = "521000", start: String = "2026-10-01T04:00:00Z", end: String = "2026-11-01T04:00:00Z", zone: String = "America/Santo_Domingo") throws -> FinancialBudgetProgress {
        try decode(FinancialBudgetProgress.self, #"""
        {"budget":{"id":"\#(UUID())","version":3,"name":"Supermercado","limit_minor":\#(limitMinor),"limit":"25000.00","currency":"DOP","currency_fraction_digits":2,"month":"2026-10","account_ids":["\#(UUID())"],"category_ids":["groceries"],"include_uncategorized":false,"archived":false},
         "period":{"month":"2026-10","time_zone":"\#(zone)","start_at":"\#(start)","end_at_exclusive":"\#(end)"},
         "gross_purchases_minor":"\#(spentMinor)","refunds_minor":"0","spent_minor":"\#(spentMinor)","remaining_minor":"1979000","over_budget_minor":"0","contributors":[]}
        """#)
    }

    private func goal(state: String = "on_track", supportedMinor: String? = "2400000", cadence: String = "monthly") throws -> FinancialGoalProgress {
        let supported = supportedMinor.map { "\"\($0)\"" } ?? "null"
        return try decode(FinancialGoalProgress.self, #"""
        {"goal":{"id":"\#(UUID())","version":2,"name":"Samaná","currency":"DOP","currency_fraction_digits":2,"target_minor":6000000,"target":"60000.00","target_date":null,"destination_account_id":"\#(UUID())",
                 "contribution_plan":{"source_account_id":"\#(UUID())","amount":"6000.00","schedule":{"cadence":"\#(cadence)","start_date":"2026-10-15","month_days":[]}},
                 "allocations":[],"archived":false,"earliest_effective_date":"2026-10-06"},
         "assigned_minor":"2400000","supported_minor":\#(supported),"independently_backed_minor":"2400000","remaining_minor":"3600000","state":"\#(state)","reasons":[],
         "pools":[],"contributions":[],"components":[],"planned_minor":"0","projected_minor":null,"projection_end_date":"2027-03-31"}
        """#)
    }

    private func debt(balanceMinor: Int64? = -4500000, state: String = "active", cadence: String = "weekly", archived: Bool = false) throws -> FinancialDebtProgress {
        let balance = balanceMinor.map(String.init) ?? "null"
        return try decode(FinancialDebtProgress.self, #"""
        {"debt":{"id":"\#(UUID())","version":4,"debt_account_id":"\#(UUID())","name":"Tarjeta","currency":"DOP","currency_fraction_digits":2,"source_account_id":"\#(UUID())",
                 "amount_minor":500000,"amount":"5000.00","schedule":{"cadence":"\#(cadence)","start_date":"2026-10-30","month_days":[]},
                 "assumptions":{"annual_rate_percent":"24.00","recurring_fees":"0.00","first_period_start":"2026-10-01","no_new_borrowing":true},"archived":\#(archived),"earliest_effective_date":"2026-10-06"},
         "balance":{"state":"known","amount_minor":\#(balance),"amount":null,"as_of":null,"basis":null,"activity_since_tracking_minor":0,"credit_minor":null},
         "state":"\#(state)","payoff":{"state":"unavailable","reason":"cadence_unsupported"},"payments":[],"occurrences":[],"funding_pool":null}
        """#)
    }

    func testBudgetScenarioCountsDaysFromTheServerPeriod() throws {
        let scenario = try XCTUnwrap(ConnectedPlanScenario.budget(try budget(), now: try instant("2026-10-06T15:00:00Z")))
        XCTAssertEqual(scenario.kind, .budget)
        XCTAssertEqual(scenario.look, .sunshine)
        XCTAssertEqual(scenario.currency, "DOP")
        XCTAssertEqual(scenario.target, 25000)
        XCTAssertEqual(scenario.recorded, 5210)
        XCTAssertEqual(scenario.monthly, 25000)
        XCTAssertEqual(scenario.budgetDays, PlanScenarioDays(elapsed: 6, total: 31))
        XCTAssertEqual(scenario.projectedValue(at: 31, monthly: 25000), 26918.333333333332, accuracy: 0.000001)
        XCTAssertEqual(scenario.disclosure(spanish: false), "Simple projection using 6 recorded days in a 31-day month. This is not confirmed spending.")
        XCTAssertEqual(scenario.disclosure(spanish: true), "Proyección simple con 6 días registrados de un mes de 31 días. No es un gasto confirmado.")
        XCTAssertEqual(scenario.budgetEdges(spanish: false).first, "Oct 1")
        XCTAssertEqual(scenario.budgetEdges(spanish: false).last, "Oct 31")
        XCTAssertEqual(scenario.budgetEdges(spanish: true).first, "1 oct.")
        XCTAssertEqual(scenario.budgetEdges(spanish: true).last, "31 oct.")
    }

    func testBudgetDaysStayInsideThePeriodInItsOwnZone() throws {
        let progress = try budget()
        let lastEvening = try XCTUnwrap(ConnectedPlanScenario.budget(progress, now: try instant("2026-11-01T03:30:00Z")))
        XCTAssertEqual(lastEvening.budgetDays, PlanScenarioDays(elapsed: 31, total: 31))
        XCTAssertEqual(lastEvening.budgetEdges(spanish: false).last, "Oct 31")
        XCTAssertEqual(lastEvening, ConnectedPlanScenario.budget(progress, now: try instant("2026-11-01T03:59:59Z")))
        XCTAssertNotEqual(lastEvening, ConnectedPlanScenario.budget(progress, now: try instant("2026-10-31T03:59:59Z")))
        let before = try XCTUnwrap(ConnectedPlanScenario.budget(progress, now: try instant("2026-09-20T12:00:00Z")))
        XCTAssertEqual(before.budgetDays, PlanScenarioDays(elapsed: 1, total: 31))
        let after = try XCTUnwrap(ConnectedPlanScenario.budget(progress, now: try instant("2026-12-15T12:00:00Z")))
        XCTAssertEqual(after.budgetDays, PlanScenarioDays(elapsed: 31, total: 31))
        XCTAssertEqual(after.budgetEdges(spanish: false).first, "Oct 1")
        let february = try XCTUnwrap(ConnectedPlanScenario.budget(try budget(start: "2027-02-01T04:00:00Z", end: "2027-03-01T04:00:00Z"), now: try instant("2027-02-10T12:00:00Z")))
        XCTAssertEqual(february.budgetDays, PlanScenarioDays(elapsed: 10, total: 28))
        XCTAssertEqual(february.budgetEdges(spanish: false).last, "Feb 28")
    }

    func testBudgetWithoutAReadablePeriodHasNoScenario() throws {
        XCTAssertNil(ConnectedPlanScenario.budget(try budget(zone: "Not/AZone"), now: try instant("2026-10-06T15:00:00Z")))
        XCTAssertNil(ConnectedPlanScenario.budget(try budget(start: "2026-10-01"), now: try instant("2026-10-06T15:00:00Z")))
        XCTAssertNil(ConnectedPlanScenario.budget(try budget(start: "2026-11-01T04:00:00Z", end: "2026-10-01T04:00:00Z"), now: try instant("2026-10-06T15:00:00Z")))
    }

    func testGoalWithAMonthlyPlanProjectsItsArrival() throws {
        let now = try instant("2026-10-06T15:00:00Z")
        let scenario = try XCTUnwrap(ConnectedPlanScenario.goal(try goal(), now: now))
        XCTAssertEqual(scenario.kind, .goal)
        XCTAssertEqual(scenario.look, .coast)
        XCTAssertEqual(scenario.target, 60000)
        XCTAssertEqual(scenario.recorded, 24000)
        XCTAssertEqual(scenario.monthly, 6000)
        XCTAssertEqual(scenario.today, Calendar.current.startOfDay(for: now))
        XCTAssertEqual(scenario.months(at: scenario.monthly), 6)
        XCTAssertEqual(scenario.months(at: 12000), 3)
        XCTAssertEqual(scenario.monthlyAmount(finishingIn: 12), 3000)
    }

    func testGoalWithoutAMonthlyPlanStartsAtZero() throws {
        let scenario = try XCTUnwrap(ConnectedPlanScenario.goal(try goal(cadence: "weekly"), now: try instant("2026-10-06T15:00:00Z")))
        XCTAssertEqual(scenario.monthly, 0)
        XCTAssertNil(scenario.months(at: scenario.monthly))
    }

    func testReachedOrUnreviewedGoalHasNoScenario() throws {
        let now = try instant("2026-10-06T15:00:00Z")
        XCTAssertNil(ConnectedPlanScenario.goal(try goal(state: "reached"), now: now))
        XCTAssertNil(ConnectedPlanScenario.goal(try goal(supportedMinor: nil), now: now))
        XCTAssertNil(ConnectedPlanScenario.goal(try goal(supportedMinor: "6000000"), now: now))
    }

    func testDebtReadsTheOwedBalanceAndItsRate() throws {
        let weekly = try XCTUnwrap(ConnectedPlanScenario.debt(try debt(), now: try instant("2026-10-06T15:00:00Z")))
        XCTAssertEqual(weekly.kind, .debt)
        XCTAssertEqual(weekly.look, .bloom)
        XCTAssertEqual(weekly.target, 45000)
        XCTAssertEqual(weekly.recorded, 0)
        XCTAssertEqual(weekly.remaining, 45000)
        XCTAssertEqual(weekly.monthly, 0)
        XCTAssertEqual(weekly.annualRate, 24)
        let monthly = try XCTUnwrap(ConnectedPlanScenario.debt(try debt(cadence: "monthly"), now: try instant("2026-10-06T15:00:00Z")))
        XCTAssertEqual(monthly.monthly, 5000)
        XCTAssertEqual(monthly.months(at: 5000), 11)
    }

    func testClearArchivedOrUnknownDebtHasNoScenario() throws {
        let now = try instant("2026-10-06T15:00:00Z")
        XCTAssertNil(ConnectedPlanScenario.debt(try debt(balanceMinor: 0, state: "recorded_clear"), now: now))
        XCTAssertNil(ConnectedPlanScenario.debt(try debt(balanceMinor: 1200), now: now))
        XCTAssertNil(ConnectedPlanScenario.debt(try debt(balanceMinor: nil, state: "unknown"), now: now))
        XCTAssertNil(ConnectedPlanScenario.debt(try debt(archived: true), now: now))
    }

    @MainActor
    func testAppliedAmountParsesBackThroughTheDraftCommand() throws {
        for (identifier, text) in [("en_US", "12,000.50"), ("es_ES", "12.000,50")] {
            let locale = Locale(identifier: identifier)
            let draft = FinancialBudgetDraft(budget: try budget().budget)
            draft.limit = ConnectedPlanScenario.draftAmount(12000.5, digits: 2, locale: locale)
            XCTAssertEqual(draft.limit, text)
            XCTAssertEqual(try AccountEntry.amount(draft.limit, locale: locale), "12000.50")
            XCTAssertEqual(try draft.command(locale: locale).limit, "12000.50")
        }
        let english = Locale(identifier: "en_US")
        XCTAssertEqual(try AccountEntry.amount(ConnectedPlanScenario.draftAmount(12000.4, digits: 0, locale: english), locale: english), "12000")
        XCTAssertEqual(try AccountEntry.amount(ConnectedPlanScenario.draftAmount(0.125, digits: 3, locale: english), locale: english), "0.125")
        XCTAssertEqual(try AccountEntry.amount(ConnectedPlanScenario.draftAmount(6000, digits: 2, locale: english), locale: english), "6000.00")
    }
}
