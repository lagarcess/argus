import Foundation
import ArgusSession

/// The one rule for adding a movement: no account starts the first-account sheet; otherwise the editor
/// opens on the first money account in the person's own order, and the editor's account row changes it,
/// so there is no list to pick from first. The editor only lists accounts in the starting account's
/// currency, so with accounts in more than one currency the person chooses first.
/// Home's Activity "+" and the navigation "+" share it.
/// Until the accounts have loaded the list says nothing, so the answer is to load first.
enum ConnectedAddMovement {
    enum Target {
        case loadAccounts
        case createAccount
        case record(FinancialAccount)
        case choose
    }

    static func target(for activeAccounts: [FinancialAccount], loaded: Bool) -> Target {
        guard loaded else { return .loadAccounts }
        guard let first = activeAccounts.first(where: { $0.nature == "asset" }) ?? activeAccounts.first else {
            return .createAccount
        }
        return Set(activeAccounts.map(\.currency)).count > 1 ? .choose : .record(first)
    }
}
