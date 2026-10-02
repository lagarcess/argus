import Foundation

@main struct ReceiptPreviewChecks {
    static func main() throws {
        var count = 0
        func check(_ value: @autoclosure () -> Bool, _ message: String) {
            precondition(value(), message); count += 1
        }
        func rejects(_ message: String, _ operation: () throws -> Void) {
            do { try operation(); preconditionFailure(message) } catch { count += 1 }
        }
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: folder) }
        let store = CuadraoReceiptStore(directory: folder.appendingPathComponent("receipts"))
        let groupFile = folder.appendingPathComponent("groups.json")
        let groups = CuadraoGroupPreview(spanish: false, defaults: nil, storageURL: groupFile)
        let accounts = CuadraoAccountsPreview(populated: true, spanish: false)
        let group = groups.groups.first!
        let source = Data("source bytes owned by the capture adapter".utf8)
        let origin = ReceiptOrigin(groupID: group.id, threadID: "captured-thread")
        let id = try store.capture(files: [(source, "receipt.jpg", false)], currency: group.currency,
                                   origin: origin, group: group, example: true, spanish: false)
        var draft = store.receipt(id)!
        check(draft.total == 289280, "Prepared sample includes tax and service exactly once")
        check(groups.group(group.id)!.total == group.total, "Capture never changes balances")
        let retainedSource = try Data(contentsOf: store.url(draft.source[0]))
        check(retainedSource == source, "Source is retained before review")
        let reopened = CuadraoReceiptStore(directory: store.directory)
        check(reopened.receipt(id) == draft, "Later and relaunch reopen the same receipt")
        check(draft.origin.threadID == "captured-thread", "Origin identity survives relaunch")
        let ids = group.activeMembers.map(\.id)
        draft.lines = [.init(name: "Shared", unitCents: 101, members: [ids[0], ids[1]]),
                       .init(name: "Own", quantity: 2, unitCents: 50, members: [ids[2]])]
        draft.taxCents = 18; draft.serviceCents = 10; draft.addedTipCents = 7
        draft.participants = Set(ids.prefix(3)); draft.split = .items
        let shares = try draft.shares(roster: ids)
        check(draft.receiptTotal == 229 && draft.total == 236, "Additional tip is distinct from included charges")
        check(shares == [ids[0]: 60, ids[1]: 59, ids[2]: 117], "Shared item and proportional charge remainders reconcile exactly")
        check(shares.values.reduce(0, +) == draft.total, "Every cent belongs to one member")
        draft.payer = ids[3]
        try store.update(draft)
        try store.confirm(id, groups: groups, accounts: accounts)
        try store.confirm(id, groups: groups, accounts: accounts)
        check(groups.group(group.id)!.expenses.filter { $0.id == id }.count == 1, "Repeated confirmation posts once")
        check(groups.group(group.id)!.expenses.first { $0.id == id }!.payer == ids[3], "Payer need not consume items")
        let loadedGroups = CuadraoGroupPreview(spanish: true, defaults: nil, storageURL: groupFile)
        check(loadedGroups.group(group.id)!.total == group.total + 236, "Group posting survives relaunch")
        rejects("Confirmed snapshots are frozen") { try store.update(draft) }
        var incomplete = draft; incomplete.lines[0].members = []
        rejects("Unassigned items block confirmation") { _ = try incomplete.shares(roster: ids) }
        incomplete = draft; incomplete.participants = []
        rejects("No participants blocks confirmation") { _ = try incomplete.shares(roster: ids) }
        incomplete = draft; incomplete.lines = []
        rejects("An empty receipt cannot post") { try incomplete.validate() }
        let personal = try store.capture(files: [(source, "personal.jpg", false)], currency: "DOP", origin: .init(groupID: nil, threadID: "personal"), group: nil, example: true, spanish: false)
        rejects("Personal account must be explicitly chosen") { try store.confirm(personal, groups: groups, accounts: accounts) }
        var personalDraft = store.receipt(personal)!
        let account = accounts.accounts.first!
        personalDraft.destination = .personal(accountID: account.id)
        try store.update(personalDraft)
        let balance = account.balance!
        try store.confirm(personal, groups: groups, accounts: accounts)
        try store.confirm(personal, groups: groups, accounts: accounts)
        check(accounts.activity.filter { $0.id == personal }.count == 1, "Personal activity posts once")
        check(accounts.account(account.id)!.balance == balance - Decimal(personalDraft.total) / 100, "Explicit account receives exact preview debit")
        let freshAccounts = CuadraoAccountsPreview(populated: true, spanish: false)
        let freshStore = CuadraoReceiptStore(directory: store.directory)
        try freshStore.reconcile(groups: loadedGroups, accounts: freshAccounts)
        try freshStore.reconcile(groups: loadedGroups, accounts: freshAccounts)
        check(freshAccounts.activity.filter { $0.id == personal }.count == 1, "Relaunch projects one personal activity")
        check(!freshAccounts.activity.contains { $0.id == id }, "Group total is not duplicated into personal activity")
        let imported = try store.capture(files: [(source, "actual.pdf", true)], currency: "USD", origin: .init(groupID: nil, threadID: nil), group: nil, example: false, spanish: false)
        check(store.receipt(imported)!.lines.isEmpty && store.receipt(imported)!.total == 0, "Arbitrary imports never receive fictional extraction")
        var incompatible = store.receipt(imported)!
        incompatible.merchant = "Actual"; incompatible.lines = [.init(name: "Item", unitCents: 10)]
        incompatible.destination = .group(group.id); incompatible.payer = group.me; incompatible.participants = Set(ids)
        try store.update(incompatible)
        rejects("A fixed currency cannot become a different group currency") { try store.confirm(imported, groups: groups, accounts: accounts) }
        let interruptedID = try store.capture(files: [(source, "interrupted.jpg", false)], currency: "DOP", origin: origin, group: group, example: true, spanish: false)
        try loadedGroups.confirmReceipt(store.receipt(interruptedID)!, groupID: group.id)
        rejects("An interrupted confirmed posting cannot lose its source") { try store.discard(interruptedID, groups: loadedGroups) }
        let recovered = CuadraoReceiptStore(directory: store.directory)
        try recovered.reconcile(groups: loadedGroups, accounts: freshAccounts)
        check(recovered.receipt(interruptedID)?.lifecycle == .confirmed, "Recovery repairs lifecycle after durable posting")
        let failDirectory = folder.appendingPathComponent("fail")
        let failing = CuadraoReceiptStore(directory: failDirectory)
        try FileManager.default.removeItem(at: failDirectory)
        try Data("not a directory".utf8).write(to: failDirectory)
        rejects("A failed source write cannot publish a receipt") {
            _ = try failing.capture(files: [(source, "failure.jpg", false)], currency: "DOP", origin: origin, group: group, example: true, spanish: false)
        }
        check(failing.receipts.isEmpty, "Failed capture leaves no indexed draft")
        let corruptDirectory = folder.appendingPathComponent("corrupt")
        try FileManager.default.createDirectory(at: corruptDirectory, withIntermediateDirectories: true)
        let corruptIndex = corruptDirectory.appendingPathComponent("receipts.json")
        try Data("corrupt".utf8).write(to: corruptIndex)
        let corrupt = CuadraoReceiptStore(directory: corruptDirectory)
        check(corrupt.loadFailed, "Corrupt receipt index is reported")
        let retainedCorrupt = try Data(contentsOf: corruptIndex)
        check(retainedCorrupt == Data("corrupt".utf8), "Corrupt evidence is not overwritten")
        let discarded = try store.capture(files: [(source, "discard.jpg", false)], currency: "DOP", origin: origin, group: group, example: false, spanish: false)
        let discardURL = store.url(store.receipt(discarded)!.source[0])
        try store.discard(discarded, groups: groups)
        check(store.receipt(discarded) == nil && !FileManager.default.fileExists(atPath: discardURL.path), "Discard removes the draft and source")
        rejects("Confirmed receipts cannot be discarded") { try store.discard(id, groups: groups) }
        print("Receipt preview checks passed: \(count)")
    }
}
