import Foundation

@main struct ReleaseUpdatesChecks {
    static func main() {
        var count = 0
        func check(_ value: Bool, _ message: String) {
            precondition(value, message)
            count += 1
        }
        check(ReleaseRecordedMonth.missingCoverage.compared(to: .recorded(0)) == .unavailable, "Missing current coverage cannot compare")
        check(ReleaseRecordedMonth.recorded(250).compared(to: .missingCoverage) == .unavailable, "Missing prior coverage cannot compare")
        check(ReleaseRecordedMonth.recorded(250).compared(to: .recorded(0)) == .amount(250), "Zero baseline uses money")
        check(ReleaseRecordedMonth.recorded(0).compared(to: .recorded(0)) == .amount(0), "Known zero stays known")
        check(ReleaseRecordedMonth.recorded(150).compared(to: .recorded(100)) == .percentage(50), "Nonzero baseline can compare")
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/Chicago")!
        func date(_ year: Int, _ month: Int, _ day: Int, _ hour: Int = 12) -> Date {
            calendar.date(from: DateComponents(year: year, month: month, day: day, hour: hour))!
        }
        for (due, earlier) in [(date(2027, 1, 1), date(2026, 12, 29)),
                              (date(2026, 3, 10), date(2026, 3, 7)),
                              (date(2026, 11, 3), date(2026, 10, 31)),
                              (date(2028, 3, 1), date(2028, 2, 27))] {
            check(ReleaseBillReminder.matching(dueDate: due, on: earlier, calendar: calendar) == .threeDaysBefore, "Calendar boundary keeps three-day reminder")
            check(ReleaseBillReminder.matching(dueDate: due, on: due, calendar: calendar) == .dueToday, "Due-day reminder")
            check(ReleaseBillReminder.matching(dueDate: due, on: calendar.date(byAdding: .day, value: -2, to: due)!, calendar: calendar) == nil, "No extra reminder on other days")
        }
        check(ReleaseBillReminder.matching(dueDate: date(2026, 10, 2, 23), on: date(2026, 10, 2, 1), calendar: calendar) == .dueToday, "Due date ignores clock time")
        check(ReleaseClosedBalance(amount: 0, currency: "DOP") == nil, "No zero closed-balance note")
        for spanish in [true, false] {
            let safe = ReleaseSafePushCopy.title(spanish: spanish) + ReleaseSafePushCopy.body(spanish: spanish)
            check(safe.rangeOfCharacter(from: .decimalDigits) == nil, "Push has no amount")
            let noBalance = ReleaseUpdateKind.formerMember(plan: "Casa", closedBalance: nil).detail(spanish: spanish)
            check(!noBalance.contains("cerrado (") && !noBalance.contains("closed ("), "No open balance omits settlement sentences")
            let nonzero = ReleaseUpdateKind.formerMember(plan: "Casa", closedBalance: ReleaseClosedBalance(amount: 50, currency: "DOP")).detail(spanish: spanish)
            check(nonzero.contains("DOP") && nonzero.contains("50"), "Signed-in source note retains nonzero balance")
        }
        print("Passed \(count) release Updates checks")
    }
}
