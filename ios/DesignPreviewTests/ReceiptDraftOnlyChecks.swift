import Foundation

@main struct ReceiptDraftOnlyChecks {
    static func main() throws {
        var count = 0
        func check(_ value: @autoclosure () -> Bool, _ message: String) {
            precondition(value(), message)
            count += 1
        }
        func postingBlocked(_ operation: () throws -> Void) throws {
            do {
                try operation()
                preconditionFailure("Draft-only storage must reject posting")
            } catch ReceiptPostingCapability.Failure.unavailable {
                count += 1
            }
        }

        let support = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: support) }
        let owner = UUID()
        let store = CuadraoReceiptStore.connectedDrafts(userID: owner, applicationSupport: support)
        let otherOwner = CuadraoReceiptStore.connectedDrafts(userID: UUID(), applicationSupport: support)
        let preview = CuadraoReceiptStore(directory: support.appendingPathComponent("CuadraoReceipts"))
        let source = Data("Source retained by the native capture adapter".utf8)
        let origin = ReceiptOrigin(groupID: nil, threadID: UUID().uuidString)
        let previewID = try preview.capture(files: [(source, "preview.jpg", false)], currency: nil,
            origin: origin, group: nil, example: false, spanish: false)
        let id = try store.capture(files: [(source, "original.pdf", true)], currency: nil,
            origin: origin, group: nil, example: false, spanish: false)
        var draft = store.receipt(id)!
        check(!store.postingCapability.allowsPosting, "Connected factory always creates a draft-only store")
        check(preview.postingCapability.allowsPosting, "Default Preview posting remains available")
        check(draft.currency == nil && draft.lines.isEmpty, "Saving a connected source invents no receipt details")
        draft.merchant = "Reviewed merchant"
        try store.update(draft)
        let reopened = CuadraoReceiptStore.connectedDrafts(userID: owner, applicationSupport: support)
        check(reopened.receipt(id) == store.receipt(id), "Draft edits survive reopening the authenticated store")
        let retained = try Data(contentsOf: reopened.url(reopened.receipt(id)!.source[0]))
        check(retained == source, "The original source survives Later and relaunch")
        check(otherOwner.receipts.isEmpty && otherOwner.directory != store.directory,
              "Another authenticated identity never reads this person's drafts")
        check(preview.receipt(id) == nil && reopened.receipt(previewID) == nil && preview.directory != store.directory,
              "Connected drafts and Preview receipts remain in separate directories")

        // Populated dependencies prove that the store gate does not rely on the wrapper's empty pickers.
        let accounts = CuadraoAccountsPreview(populated: true, spanish: false)
        let groups = CuadraoGroupPreview(spanish: false, defaults: nil)
        let account = accounts.accounts.first!
        let group = groups.groups.first!
        let balances = accounts.accounts.map(\.balance)
        let activity = accounts.activity.map(\.id)
        let originalGroups = groups.groups
        var groupReceiptID: UUID?
        for destination in [ReceiptDestination.personal(accountID: account.id), .group(group.id)] {
            let isGroup: Bool
            switch destination { case .group: isGroup = true; case .personal: isGroup = false }
            let target = isGroup ? group : nil
            let receiptID = try store.capture(files: [(source, "review.jpg", false)], currency: account.currency,
                origin: .init(groupID: target?.id, threadID: origin.threadID), group: target,
                example: true, spanish: false)
            var ready = store.receipt(receiptID)!
            ready.destination = destination
            try ready.validate()
            try store.update(ready)
            let before = store.receipt(receiptID)
            try postingBlocked { try store.confirm(receiptID, groups: groups, accounts: accounts) }
            check(store.receipt(receiptID) == before, "Blocked confirmation preserves the complete draft")
            if isGroup { groupReceiptID = receiptID }
        }
        check(accounts.activity.map(\.id) == activity && accounts.accounts.map(\.balance) == balances,
              "Blocked personal confirmation changes no activity or balance")
        check(groups.groups == originalGroups, "Blocked group confirmation adds no expense")

        // An existing group posting cannot make draft-only reconciliation change receipt state.
        let interrupted = store.receipt(groupReceiptID!)!
        try groups.confirmReceipt(interrupted, groupID: group.id)
        try postingBlocked { try store.reconcile(groups: groups, accounts: accounts) }
        check(store.receipt(interrupted.id) == interrupted, "Draft-only reconciliation cannot confirm a receipt")

        // Even a previously confirmed Preview snapshot cannot be projected by a draft-only store.
        let confirmedID = try preview.capture(files: [(source, "confirmed.jpg", false)], currency: account.currency,
            origin: origin, group: nil, example: true, spanish: false)
        var confirmed = preview.receipt(confirmedID)!
        confirmed.destination = .personal(accountID: account.id)
        try preview.update(confirmed)
        try preview.confirm(confirmedID, groups: groups, accounts: accounts)
        let projectionTarget = CuadraoAccountsPreview(populated: false, spanish: false)
        projectionTarget.accounts = [account]
        let restricted = CuadraoReceiptStore(directory: preview.directory, postingCapability: .draftOnly)
        check(restricted.receipt(confirmedID)?.prepared == false, "Projection test loads an actually confirmed receipt")
        restricted.projectPersonal(into: projectionTarget)
        check(projectionTarget.activity.isEmpty && projectionTarget.account(account.id)?.balance == account.balance,
              "Draft-only projection cannot create personal activity or alter a balance")

        let originalURL = store.url(store.receipt(id)!.source[0])
        try store.discard(id, groups: groups)
        check(store.receipt(id) == nil && !FileManager.default.fileExists(atPath: originalURL.path),
              "Discard still removes a connected draft and its source")
        check(CuadraoReceiptStore.connectedDrafts(userID: owner, applicationSupport: support).receipt(id) == nil,
              "Discard remains durable when the person returns")
        print("Receipt draft-only checks passed: \(count)")
    }
}
