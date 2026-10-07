import Foundation
import ArgusSession

/// The one rule for adding a movement: no account starts the first-account sheet, one account
/// opens its editor, several ask which account. Home's Activity "+" and the navigation "+" share it.
enum ConnectedAddMovement {
    enum Target {
        case createAccount
        case record(FinancialAccount)
        case choose
    }

    static func target(for activeAccounts: [FinancialAccount]) -> Target {
        switch activeAccounts.count {
        case 0: .createAccount
        case 1: .record(activeAccounts[0])
        default: .choose
        }
    }
}
