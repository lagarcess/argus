import Foundation
import ArgusSession

// Feeds the local what-if from server-owned plan values; nil means the Preview shows its landscape instead.
enum ConnectedPlanScenario {
    static func budget(_ progress: FinancialBudgetProgress, now: Date) -> PlanScenario? {
        let period = progress.period, budget = progress.budget
        guard let zone = TimeZone(identifier: period.timeZone),
              let start = AccountPresentation.parseDate(period.startAt),
              let end = AccountPresentation.parseDate(period.endAtExclusive), start < end,
              let limit = value(String(budget.limitMinor), digits: budget.currencyFractionDigits),
              let spent = value(progress.spentMinor, digits: budget.currencyFractionDigits) else { return nil }
        var calendar = Calendar(identifier: .gregorian); calendar.timeZone = zone
        guard let total = calendar.dateComponents([.day], from: start, to: end).day, total > 0 else { return nil }
        let today = calendar.startOfDay(for: min(max(now, start), end.addingTimeInterval(-1)))
        let index = calendar.dateComponents([.day], from: calendar.startOfDay(for: start), to: today).day ?? 0
        return PlanScenario(kind: .budget, currency: budget.currency, target: limit, recorded: spent, monthly: limit, look: .sunshine,
            budgetDays: .init(elapsed: min(total, max(1, index + 1)), total: total), today: today, timeZone: zone)
    }

    static func goal(_ progress: FinancialGoalProgress, now: Date) -> PlanScenario? {
        let goal = progress.goal
        guard progress.state != "reached", let supported = progress.supportedMinor,
              let target = value(String(goal.targetMinor), digits: goal.currencyFractionDigits),
              let recorded = value(supported, digits: goal.currencyFractionDigits) else { return nil }
        let monthly = goal.contributionPlan.flatMap { $0.schedule.cadence == .monthly ? Decimal(string: $0.amount, locale: posix) : nil }
        let scenario = PlanScenario(kind: .goal, currency: goal.currency, target: target, recorded: recorded,
            monthly: monthly.map(double) ?? 0, look: .coast, today: Calendar.current.startOfDay(for: now))
        return scenario.remaining > 0 ? scenario : nil
    }

    static func debt(_ progress: FinancialDebtProgress, now: Date) -> PlanScenario? {
        let debt = progress.debt
        guard !debt.archived, progress.state != "recorded_clear", let balance = progress.balance.amountMinor, balance < 0,
              let owed = value(String(balance.magnitude), digits: debt.currencyFractionDigits) else { return nil }
        let monthly = debt.schedule.cadence == .monthly ? value(String(debt.amountMinor), digits: debt.currencyFractionDigits) : nil
        return PlanScenario(kind: .debt, currency: debt.currency, target: owed, recorded: 0, monthly: monthly ?? 0,
            annualRate: debt.assumptions.flatMap { Double($0.annualRatePercent) } ?? 0, look: .bloom, today: Calendar.current.startOfDay(for: now))
    }

    static func draftAmount(_ amount: Double, digits: Int, locale: Locale) -> String {
        var exact = Decimal(amount) * pow(10, digits), rounded = Decimal()
        NSDecimalRound(&rounded, &exact, 0, .plain)
        return AccountPresentation.amount(AccountPresentation.decimal(NSDecimalNumber(decimal: rounded).stringValue, digits: digits), locale: locale)
    }

    private static let posix = Locale(identifier: "en_US_POSIX")
    private static func value(_ minor: String, digits: Int) -> Double? {
        Decimal(string: AccountPresentation.decimal(minor, digits: digits), locale: posix).map(double)
    }
    private static func double(_ value: Decimal) -> Double { NSDecimalNumber(decimal: value).doubleValue }
}
