import Foundation

@main enum HomeBalanceChecks {
    static func main() {
        var checks = 0
        func check(_ condition: Bool, _ title: String) {
            precondition(condition, title); checks += 1
        }
        let now = Date(timeIntervalSince1970: 1790870400)
        var cash = CanvasAccount(name: "Cash", kind: .cash, balance: 1000)
        let debt = CanvasAccount(name: "Debt", kind: .loan, balance: 200)
        let asset = CanvasAccount(name: "Asset", kind: .property, balance: 800, share: 25)
        let unknown = CanvasAccount(name: "Unknown", kind: .checking, balance: nil)
        check(CanvasBalanceHistory.position([cash,debt,asset]) == 1000, "Debt signs and asset ownership")
        check(CanvasBalanceHistory.position([unknown]) == nil, "Unknown is not zero")
        check(CanvasBalanceHistory.position([cash,unknown]) == 1000, "Partial known position")
        check(CanvasBalanceHistory.position([]) == nil, "Empty position")
        let fixture = CanvasBalanceHistory.examples(accounts: [cash,debt,asset], now: now)
        let points = CanvasBalanceHistory.points(accounts: [cash,debt,asset], observations: fixture, now: now)
        check(points.count > 9, "Sample history extends beyond the compact window")
        let recent = CanvasHomeRange.month.points(points, now: now)
        check(recent.count >= 9 && recent.allSatisfy { $0.date >= CanvasHomeRange.month.start(now: now)! }, "Rolling month retains only observations within its window")
        check(CanvasHomeRange.all.points(points, now: now) == points, "All retains available history")
        let oldest = CanvasHistoryRange.month.oldestOffset(points, now: now)
        let januaryPoints = CanvasHistoryRange.month.points(points, now: now, offset: oldest)
        check(januaryPoints.count >= 8 && januaryPoints.count < 20, "A specific month isolates its recorded observations")
        check(januaryPoints.allSatisfy { Calendar.current.component(.month, from: $0.date) == 1 }, "No present-day point appended to a past month")
        check(CanvasHomeRange.quarter.points(points, now: now).count > recent.count, "Quarter widens the visible window")
        check(CanvasHistoryRange.year.points(points, now: now).allSatisfy { Calendar.current.component(.year, from: $0.date) == 2026 }, "Year excludes prior years")
        check(CanvasHomeRange.available(points, now: now).contains(.halfYear), "Covered rolling windows are offered")
        check(CanvasHomeRange.available(points, now: now).contains(.year), "Full previous year makes annual history available")
        check(CanvasHistoryRange.month.interval(now: now, offset: 2) == CanvasHistoryRange.month.interval(now: now), "No future calendar period")
        check(CanvasHistoryRange.month.baseline(points, now: now)?.date ?? now < now, "Comparison uses a real earlier observation")
        check(CanvasHistoryRange.week.oldestOffset(points, now: now) < -30, "Week pagination spans available history")
        check(points.last?.balance == 1000, "Chart endpoint is the summary owner")
        check(points.map(\.date) == points.map(\.date).sorted(), "Chronological points")
        check(points.allSatisfy { $0.date <= now }, "Never a forecast")
        let newcomer = CanvasAccount(name: "New", kind: .savings, balance: 100)
        check(CanvasBalanceHistory.points(accounts: [cash,newcomer], observations: fixture, now: now).count == 1, "No invented history for new accounts")
        check(CanvasBalanceHistory.points(accounts: [unknown], observations: fixture, now: now).isEmpty, "No line for all-unknown")
        check(CanvasBalanceHistory.points(accounts: [cash], observations: fixture, now: now).last?.balance == 1000, "Scope excludes debt and asset")
        cash.currency = "USD"
        check(CanvasBalanceHistory.points(accounts: [cash], observations: fixture, now: now).count == 1, "Currency changes never relabel old history")
        cash.currency = "DOP"; cash.kind = .loan
        check(CanvasBalanceHistory.points(accounts: [cash], observations: fixture, now: now).count == 1, "Kind changes never reinterpret history")
        cash.kind = .cash; cash.balance = -500
        check(CanvasBalanceHistory.points(accounts: [cash], observations: fixture, now: now).last?.balance == -500, "Negative current balance retained")
        let flat = CanvasBalanceHistory.points(accounts: [newcomer], observations: [], now: now)
        check(flat.count == 1 && flat[0].balance == 100, "Single observation does not pretend to be a trend")
        let day = Calendar.current.startOfDay(for: now)
        let earlierDay = Calendar.current.date(byAdding: .day, value: -1, to: day)!
        let dollars = CanvasAccount(name: "USD", kind: .cash, currency: "USD", balance: 40)
        let rows = [
            CanvasActivity(accountID: cash.id, title: "Food", amount: 30, date: earlierDay, income: false, category: .food),
            CanvasActivity(accountID: cash.id, title: "Home", amount: 70, date: earlierDay, income: false, category: .home),
            CanvasActivity(accountID: cash.id, title: "Income", amount: 200, date: earlierDay, income: true),
            CanvasActivity(accountID: dollars.id, title: "Other currency", amount: 99, date: earlierDay, income: false),
            CanvasActivity(accountID: cash.id, title: "Future", amount: 88, date: now.addingTimeInterval(86400), income: false)
        ]
        let expenses = CanvasSpendingHistory.expenses(rows, accounts: [cash, dollars], currency: "DOP", now: now)
        check(expenses.count == 2 && CanvasSpendingHistory.total(expenses) == 100, "Only expenses in selected currency through now")
        check(CanvasSpendingHistory.expenses(rows, accounts: [dollars], currency: "DOP", now: now).isEmpty, "Other spaces excluded")
        let buckets = CanvasSpendingHistory.buckets(expenses, range: .month)
        check(buckets.count == 2 && Set(buckets.map(\.date)).count == 1, "Shared day stacks by category")
        check(buckets.reduce(Decimal.zero) { $0 + $1.amount } == 100, "Category stacks reconcile with expense total")
        check(CanvasSpendingHistory.entries(expenses, in: DateInterval(start: earlierDay, end: day)).count == 2, "Previous period owns boundary entries")
        check(CanvasSpendingHistory.entries(expenses, in: DateInterval(start: day, end: day.addingTimeInterval(86400))).isEmpty, "Current period does not repeat previous entries")
        let sampleExpenses = CanvasSpendingHistory.examples(accounts: [cash], spanish: true, now: now)
        let sampleDays = Set(sampleExpenses.map { Calendar.current.startOfDay(for: $0.date) })
        check(sampleDays.count > 50 && sampleDays.count < CanvasPreviewHistory.days(now: now).count / 2, "Spending has quiet days rather than a transaction every day")
        let previousYear = CanvasHistoryRange.year.interval(now: now, offset: -1)
        let annual = CanvasSpendingHistory.buckets(CanvasSpendingHistory.entries(sampleExpenses, in: previousYear), range: .year)
        check(Set(annual.map(\.date)).count == 12, "Previous year fills every monthly bar")
        check(sampleExpenses.allSatisfy { $0.date < day }, "Dense samples never populate future days")
        let comparison = CanvasSpendingHistory.comparisonInterval(range: .month, offset: 0, now: now)
        check(comparison.end <= CanvasHistoryRange.month.interval(now: now, offset: -1).end, "Comparable elapsed period is bounded")
        let snapshot = CanvasBalanceHistory.snapshot(accounts: [asset], observations: fixture, at: fixture.first!.date)
        check(snapshot.first?.balance == fixture.first(where: { $0.accountID == asset.id })?.balance, "Historical allocation uses its own dated observation")
        print("Passed \(checks) Home balance projection checks")
    }
}
