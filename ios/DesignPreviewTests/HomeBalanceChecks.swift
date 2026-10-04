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
        let calendar = Calendar.current
        let month = CanvasHistoryRange.month.interval(now: now, offset: -1)
        let slots = CanvasSpendingHistory.slots(in: month, range: .month)
        check((4...6).contains(slots.count) && slots.first?.start == month.start && slots.last?.end == month.end, "Month has clipped calendar weeks covering exactly the month")
        check(zip(slots, slots.dropFirst()).allSatisfy { $0.end == $1.start }, "Weekly buckets have no gaps or overlaps")
        let monthRows = CanvasSpendingHistory.entries(sampleExpenses, in: month)
        let monthlyBuckets = CanvasSpendingHistory.buckets(monthRows, range: .month)
        check(monthlyBuckets.allSatisfy { bucket in slots.contains { $0.start == bucket.date } }, "Every expense maps into its own month week")
        check(monthlyBuckets.reduce(Decimal.zero) { $0 + $1.amount } == CanvasSpendingHistory.total(monthRows), "Weekly grouping preserves the monthly total")
        let start = calendar.date(from: DateComponents(year: 2026, month: 1, day: 1))!
        let midday = calendar.date(from: DateComponents(year: 2026, month: 10, day: 1, hour: 12))!
        let priorMorning = calendar.date(from: DateComponents(year: 2026, month: 9, day: 1, hour: 9))!
        let priorEvening = calendar.date(from: DateComponents(year: 2026, month: 9, day: 1, hour: 18))!
        let currentMorning = calendar.date(from: DateComponents(year: 2026, month: 10, day: 1, hour: 9))!
        let storyRows = [
            CanvasActivity(accountID: cash.id, title: "Prior morning", amount: 10, date: priorMorning, income: false, category: .food),
            CanvasActivity(accountID: cash.id, title: "Prior evening", amount: 900, date: priorEvening, income: false, category: .food),
            CanvasActivity(accountID: cash.id, title: "Current", amount: 30, date: currentMorning, income: false, category: .food)
        ]
        let story = CanvasSpendingStory(expenses: storyRows, range: .month, offset: 0, coverageStart: start, now: midday)
        check(story.total == 30 && story.previousTotal == 10, "First day compares the same elapsed hours, excluding previous evening")
        check(story.changedCategory == .food && story.largestExpense == nil, "One expense does not generate a redundant largest-expense highlight")
        let unknownStory = CanvasSpendingStory(expenses: storyRows, range: .month, offset: 0, coverageStart: nil, now: midday)
        check(!unknownStory.covered && unknownStory.previousTotal == nil && unknownStory.changedCategory == nil, "A recorded transaction never proves complete comparison coverage")
        let emptyStory = CanvasSpendingStory(expenses: [], range: .month, offset: 0, coverageStart: start, now: midday)
        check(emptyStory.covered && emptyStory.total == 0 && emptyStory.changedCategory == nil && emptyStory.largestExpense == nil, "Covered empty period has zero and no manufactured highlights")
        let shortHistory = CanvasSpendingStory(expenses: storyRows, range: .month, offset: 0, coverageStart: currentMorning, now: midday)
        check(!shortHistory.covered && shortHistory.previousTotal == nil, "Partial current coverage suppresses comparisons")
        let monthEnd = calendar.date(from: DateComponents(year: 2026, month: 5, day: 31, hour: 12))!
        let unequal = CanvasSpendingStory(expenses: [], range: .month, offset: 0, coverageStart: start, now: monthEnd)
        check(unequal.comparison == nil, "A 31st day never compares against a shorter completed month")
        let coverage = calendar.date(from: DateComponents(year: 2025, month: 1, day: 1))!
        let historyRows = (0..<12).map { index in
            CanvasActivity(accountID: cash.id, title: "Monthly", amount: index < 9 ? 100 : 400,
                date: calendar.date(byAdding: .month, value: index, to: coverage)!, income: false, category: .food)
        }
        let january = calendar.date(from: DateComponents(year: 2026, month: 1, day: 15))!
        let annualStory = CanvasSpendingStory(expenses: historyRows, range: .month, offset: 0, coverageStart: coverage, now: january)
        let trend = annualStory.longitudinalInsights.first { $0.kind == .trend && $0.category == .food }
        check(trend?.priorAverage == 100 && trend?.recentAverage == 400 && trend?.difference == 300, "Recent three months compare with the preceding nine from records")
        let average = annualStory.longitudinalInsights.first { $0.kind == .average && $0.category == nil && $0.months.count == 12 }
        check(average?.average == 175, "Twelve complete monthly totals have an exact arithmetic average")
        check(annualStory.completedMonths(count: 6)?.last?.interval.end == calendar.date(from: DateComponents(year: 2026, month: 1, day: 1)), "Running month excluded from completed averages")
        let sparse = CanvasSpendingStory(expenses: [historyRows.last!], range: .month, offset: 0, coverageStart: coverage, now: january)
        check(sparse.longitudinalInsights.first(where: { $0.category == nil && $0.months.count == 12 })?.average == Decimal(400) / 12, "Covered zero months stay in the average denominator")
        check(sparse.completedMonths(count: 12)?.filter { $0.amount == 0 }.count == 11, "Confirmed coverage includes months with no spending as zero")
        check(!sparse.longitudinalInsights.contains(where: { $0.kind == .trend }), "An isolated expense does not claim a sustained category trend")
        check(unknownStory.longitudinalInsights.isEmpty, "Unknown coverage never produces longitudinal insight")
        check(emptyStory.longitudinalInsights.isEmpty, "All-zero history does not manufacture a pattern")
        let historical = CanvasSpendingStory(expenses: historyRows, range: .month, offset: -4, coverageStart: coverage, now: january)
        check(historical.completedMonths(count: 6)?.last?.interval.end == calendar.date(from: DateComponents(year: 2025, month: 10, day: 1)), "Past pages exclude later records from their average")
        check(historical.completedMonths(count: 12) == nil, "A window beginning before coverage is unavailable")
        let noPriorRecords = CanvasSpendingStory(expenses: [historyRows.last!], range: .month, offset: -1, coverageStart: coverage, now: january)
        check(noPriorRecords.previousTotal == 0, "A prior covered month without spending is a known zero baseline")
        let missingCoverage = CanvasSpendingStory(expenses: [historyRows.last!], range: .month, offset: -1, coverageStart: nil, now: january)
        check(missingCoverage.previousTotal == nil && missingCoverage.completedMonths(count: 6) == nil, "Absent coverage never fills missing periods with zero")
        let zeroRows = historyRows.map { entry in
            CanvasActivity(accountID: entry.accountID, title: entry.title, amount: 0, date: entry.date, income: false, category: entry.category)
        }
        let recordedZeros = CanvasSpendingStory(expenses: zeroRows, range: .month, offset: -1, coverageStart: coverage, now: january)
        check(recordedZeros.previousTotal == 0 && recordedZeros.state == .populated, "Recorded zeros remain real observations")
        check(recordedZeros.completedMonths(count: 6)?.allSatisfy { $0.amount == 0 } == true, "Recorded zero months remain present in complete series")
        let annualHistorical = CanvasSpendingStory(expenses: historyRows, range: .year, offset: -1, coverageStart: coverage, now: january)
        check(annualHistorical.completedMonths(count: 12)?.last?.amount == 400, "A completed historical year includes its December")
        let october = calendar.date(from: DateComponents(year: 2026, month: 10, day: 15, hour: 12))!
        let septemberEnd = calendar.date(from: DateComponents(year: 2026, month: 9, day: 30))!
        let octoberFifth = calendar.date(from: DateComponents(year: 2026, month: 10, day: 5))!
        let octoberTenth = calendar.date(from: DateComponents(year: 2026, month: 10, day: 10))!
        let wallet = CanvasAccount(name: "Wallet", kind: .cash, balance: 800)
        let mortgage = CanvasAccount(name: "Mortgage", kind: .loan, balance: 150)
        let owned = CanvasAccount(name: "Shared property", kind: .property, balance: 1000, share: 25)
        let scoped = [wallet, mortgage, owned]
        func observed(_ account: CanvasAccount, _ amount: Decimal, _ date: Date) -> CanvasBalanceObservation {
            CanvasBalanceObservation(accountID: account.id, currency: account.currency, kind: account.kind,
                share: account.share, date: date, balance: amount)
        }
        let startingBalances = [observed(wallet, 1000, septemberEnd), observed(mortgage, 200, septemberEnd), observed(owned, 800, septemberEnd)]
        let period = CanvasBalancePeriod(accounts: scoped, observations: startingBalances, range: .month, offset: 0, now: october)
        check(period.opening?.balance == 1000 && period.closing?.balance == 900 && period.change == -100, "One pair of snapshots owns opening, closing and net change")
        check(period.changes.map { $0.change! } == [-200, 50, 50], "Debt paydown and partial asset ownership contribute with their true signs")
        check(period.changes.compactMap(\.change).reduce(0, +) == period.change, "Account changes exactly reconcile to displayed net change")
        check(CanvasBalanceHistory.position(period.closingAccounts) == period.closing?.balance, "Allocation and line hero use the same closing snapshot")
        let scopedPeriod = CanvasBalancePeriod(accounts: [wallet], observations: startingBalances, range: .month, offset: 0, now: october)
        check(scopedPeriod.change == -200 && scopedPeriod.changes.count == 1, "Scope excludes other account contributions")
        let partialPeriod = CanvasBalancePeriod(accounts: scoped + [unknown], observations: startingBalances, range: .month, offset: 0, now: october)
        check(partialPeriod.isPartial && partialPeriod.changes.last?.closing == nil && partialPeriod.change == -100, "Unknown account remains unknown while known rows reconcile")
        let freshPeriod = CanvasBalancePeriod(accounts: scoped + [newcomer], observations: startingBalances, range: .month, offset: 0, now: october)
        check(freshPeriod.opening == nil && freshPeriod.change == nil && freshPeriod.closing?.balance == 1000, "New account cannot inherit or zero-fill a historical opening")
        let noBaseline = CanvasBalancePeriod(accounts: [wallet], observations: [], range: .month, offset: 0, now: october)
        check(noBaseline.opening == nil && noBaseline.change == nil && noBaseline.closing?.balance == 800, "A single observation is a starting point, never a zero trend")
        let partialWindow = CanvasBalancePeriod(accounts: [wallet], observations: [observed(wallet, 900, octoberFifth)], range: .month, offset: 0, now: october)
        check(partialWindow.opening?.date == octoberFifth && partialWindow.change == -100, "Two in-period observations compare from their actual first date")
        let equalWindow = CanvasBalancePeriod(accounts: [wallet], observations: [observed(wallet, 800, octoberTenth)], range: .month, offset: 0, now: october)
        check(equalWindow.change == 0, "Two genuine equal observations support an unchanged balance")
        let november = calendar.date(from: DateComponents(year: 2026, month: 11, day: 15))!
        let quietPast = CanvasBalancePeriod(accounts: scoped, observations: startingBalances, range: .month, offset: -1, now: november)
        check(quietPast.closing?.date == septemberEnd && quietPast.change == nil, "Empty past period retains a dated known position without artificial change")
        check(CanvasBalanceHistory.position(quietPast.closingAccounts) == quietPast.closing?.balance, "Empty historical allocation preserves the same known dated snapshot")
        var clearedMortgage = mortgage
        clearedMortgage.balance = nil
        let historicalBalances = startingBalances + [observed(wallet, 900, octoberTenth), observed(mortgage, 170, octoberTenth), observed(owned, 900, octoberTenth)]
        let clearedPeriod = CanvasBalancePeriod(accounts: [wallet, clearedMortgage, owned], observations: historicalBalances, range: .month, offset: -1, now: november)
        check(clearedPeriod.changes.first { $0.id == mortgage.id }?.closing == nil, "Cleared current balance remains excluded despite old observations")
        check(CanvasBalanceHistory.position(clearedPeriod.closingAccounts) == clearedPeriod.closing?.balance, "Historical allocation preserves aggregate participation after balance clearing")
        check(clearedPeriod.changes.compactMap(\.change).reduce(0, +) == clearedPeriod.change, "Historical changes reconcile after clearing an observed account")
        let unknowable = CanvasBalancePeriod(accounts: [unknown], observations: [], range: .month, offset: 0, now: october)
        func sameWithBuiltHistory(_ accounts: [CanvasAccount], _ observations: [CanvasBalanceObservation], _ now: Date) -> Bool {
            let built = CanvasBuiltBalanceHistory(accounts: accounts, observations: observations, now: now)
            let later = calendar.date(byAdding: .hour, value: 23, to: calendar.startOfDay(for: now))!
            guard built.points(on: later) == built.points, built.points(on: later.addingTimeInterval(3600)) == nil,
                built.points == CanvasBalanceHistory.points(accounts: accounts, observations: observations, now: later) else { return false }
            return CanvasHistoryRange.allCases.allSatisfy { range in
                (-14...0).allSatisfy { offset in
                    let own = CanvasBalancePeriod(accounts: accounts, observations: observations, range: range, offset: offset, now: later)
                    let given = CanvasBalancePeriod(accounts: accounts, observations: observations, range: range, offset: offset, now: later, history: built.points)
                    return own.interval == given.interval && own.opening == given.opening && own.closing == given.closing
                        && own.isPartial == given.isPartial && own.change == given.change
                        && own.closingAccounts.map(\.id) == given.closingAccounts.map(\.id)
                        && own.closingAccounts.map(\.balance) == given.closingAccounts.map(\.balance)
                        && own.changes.map(\.id) == given.changes.map(\.id) && own.changes.map(\.opening) == given.changes.map(\.opening)
                        && own.changes.map(\.closing) == given.changes.map(\.closing)
                }
            }
        }
        check(sameWithBuiltHistory(scoped, startingBalances, october) && sameWithBuiltHistory(scoped + [unknown, newcomer], historicalBalances, november)
            && sameWithBuiltHistory([wallet, clearedMortgage, owned], historicalBalances, november) && sameWithBuiltHistory([unknown], [], october)
            && sameWithBuiltHistory([wallet], [observed(wallet, 900, octoberFifth), observed(wallet, 800, octoberTenth)], november),
            "A period given the history built earlier that day equals the period that builds its own")
        check(unknowable.closing == nil && unknowable.change == nil, "Unknown balance never becomes zero")
        check(emptyStory.state == .emptyPeriod && unknownStory.state == .populated, "Known empty and partial populated spending use distinct states")
        let firstUse = CanvasSpendingStory(expenses: [], range: .month, offset: 0, coverageStart: nil, now: october)
        check(firstUse.state == .firstUse && firstUse.previousTotal == nil, "No spending history is first use without invented comparisons")
        let unavailablePeriod = CanvasSpendingStory(expenses: historyRows, range: .month, offset: 0, coverageStart: nil, now: october)
        check(unavailablePeriod.state == .unavailable, "Existing spending elsewhere with missing coverage is not a first-use or zero month")
        print("Passed \(checks) Home balance projection checks")
    }
}
