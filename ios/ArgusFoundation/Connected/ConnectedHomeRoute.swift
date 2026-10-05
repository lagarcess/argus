import Foundation

/// Home's pushed destinations. Account routes mirror the accounts selection;
/// activity routes never touch it, so popping a movement cannot re-push an account.
enum ConnectedHomeRoute: Hashable {
    case account(UUID)
    case activity(UUID)

    var accountID: UUID? {
        if case .account(let id) = self { return id }
        return nil
    }
}
