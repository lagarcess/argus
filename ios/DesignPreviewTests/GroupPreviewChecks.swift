import Foundation

@main struct GroupPreviewChecks {
    static func main() {
        var count = 0
        func check(_ condition: @autoclosure () -> Bool, _ message: String) {
            precondition(condition(), message); count += 1
        }
        let suite = "cuadrao.group.tests.\(UUID())"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let store = CuadraoGroupPreview(spanish: true, defaults: defaults, reset: true)
        var group = store.groups.first!
        let ids = group.members.map(\.id)
        for cents in [1, 7, 100, 10001] {
            let split = PlanSharedExpense.equal(cents, among: ids)
            check(split.values.reduce(0, +) == cents, "Every cent is assigned once")
            check(split.values.max()! - split.values.min()! <= 1, "Equal split differs by at most one cent")
        }
        let oldShare = group.share(group.me), oldTotal = group.total
        var unreviewed = PlanSharedExpense(title: "Receipt to review", cents: 0, payer: group.me, shares: [:], draft: true)
        check(group.record(unreviewed), "A receipt can be saved before entering its total")
        check(group.total == oldTotal, "Unreviewed receipt does not affect balances")
        unreviewed.draft = false
        check(!group.record(unreviewed), "Unreviewed receipt cannot be published")
        group.expectedPeople += 5
        check(group.share(group.me) == oldShare && group.total == oldTotal, "Estimates do not create debt")
        var draft = PlanSharedExpense(title: "Receipt", cents: 10001, payer: ids[0], shares: [:], draft: true)
        check(group.record(draft), "Incomplete split can be kept as a draft")
        check(group.total == oldTotal, "Draft does not change group total")
        draft.draft = false
        check(!group.record(draft), "Published split must account for the entire amount")
        draft.shares = PlanSharedExpense.equal(draft.cents, among: ids)
        check(group.record(draft), "Draft can be published")
        check(group.record(draft) && group.total == oldTotal + draft.cents, "Retrying a correction does not duplicate expense")
        draft.cents += 200; draft.shares = PlanSharedExpense.equal(draft.cents, among: ids)
        check(group.record(draft) && group.total == oldTotal + draft.cents, "Editing replaces the original expense")
        check(ids.map { group.balance($0) }.reduce(0, +) == 0, "Shared balances conserve money")
        let due = -group.balance(ids[1]), receivable = group.balance(ids[0])
        check(!group.repay(from: ids[1], to: ids[0], cents: due + 1), "Cannot overpay a debt")
        check(group.repay(from: ids[1], to: ids[0], cents: due / 2), "Partial repayment is supported")
        check(group.balance(ids[1]) == -due + due / 2 && group.balance(ids[0]) == receivable - due / 2, "Both balances reflect the same repayment")
        check(group.total == oldTotal + draft.cents && group.share(ids[0]) == oldShare + draft.shares[ids[0]]!, "Repayment is not another expense")
        check(ids.map { group.balance($0) }.reduce(0, +) == 0, "Repayment conserves balances")
        group.repayments.removeLast()
        check(group.balance(ids[1]) == -due, "Undo restores the amount owed")
        group.members.append(.init(name: "New guest", symbol: "star"))
        check(group.share(group.members.last!.id) == 0, "Joining does not inherit old expenses")
        store.save(group); store.archive(group.id, true)
        let loaded = CuadraoGroupPreview(spanish: false, defaults: defaults)
        check(loaded.group(group.id)?.archived == true, "Archive persists")
        loaded.archive(group.id, false)
        check(loaded.group(group.id)?.expenses == group.expenses, "Restore preserves split corrections")
        check(loaded.groups.last!.members.allSatisfy { loaded.groups.last!.balance($0.id) == 0 }, "Saving together is not borrowing")
        loaded.resetExamples(spanish: true, empty: true)
        check(loaded.groups.isEmpty, "Cold start is genuinely empty")
        print("Passed \(count) group preview checks")
    }
}
