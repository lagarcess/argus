import Foundation
import ArgusSession

/// The one rule for adding a movement: no account starts the first-account sheet, one account
/// opens its editor, several ask which account. Home's Activity "+" and the navigation "+" share it.
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
        switch activeAccounts.count {
        case 0: return .createAccount
        case 1: return .record(activeAccounts[0])
        default: return .choose
        }
    }
}
