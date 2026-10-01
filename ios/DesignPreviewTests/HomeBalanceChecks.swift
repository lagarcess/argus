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
        check(januaryPoints.count == 4, "A specific month isolates its recorded observations")
        check(januaryPoints.allSatisfy { Calendar.current.component(.month, from: $0.date) == 1 }, "No present-day point appended to a past month")
        check(CanvasHomeRange.quarter.points(points, now: now).count > recent.count, "Quarter widens the visible window")
        check(CanvasHistoryRange.year.points(points, now: now).allSatisfy { Calendar.current.component(.year, from: $0.date) == 2026 }, "Year excludes prior years")
        check(CanvasHomeRange.available(points, now: now).contains(.halfYear), "Covered rolling windows are offered")
        check(!CanvasHomeRange.available(points, now: now).contains(.year), "Uncovered year is not offered")
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
        print("Passed \(checks) Home balance projection checks")
    }
}
