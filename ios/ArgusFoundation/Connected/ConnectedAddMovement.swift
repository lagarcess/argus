import Foundation
import ArgusSession

/// The one rule for adding a movement: no account starts the first-account sheet; otherwise the editor
/// opens on the first account in the person's own order, and the editor's account row changes it. There
/// is no list to pick from first. Home's Activity "+" and the navigation "+" share it.
/// Until the accounts have loaded the list says nothing, so the answer is to load first.
enum ConnectedAddMovement {
    enum Target {
        case loadAccounts
        case createAccount
        case record(FinancialAccount)
    }

    static func target(for activeAccounts: [FinancialAccount], loaded: Bool) -> Target {
        guard loaded else { return .loadAccounts }
        guard let first = activeAccounts.first else { return .createAccount }
        return .record(first)
    }
}
