import SwiftUI

/// Shared account actions for Home, Search and insights navigation.
enum CanvasAccountSheet: Identifiable {
    case archive(UUID), rename(UUID), record(UUID), manageAccounts(editing: Bool), archived
    var id: String { "account-modal" }
}

struct CuadraoAccountModal: View {
    let data: CuadraoAccountsPreview
    let selection: CanvasAccountSheet
    let spanish: Bool
    let show: (CanvasAccountSheet) -> Void
    let archived: (UUID) -> Void
    var body: some View {
        switch selection {
        case .archive(let id):
            CuadraoArchiveAccountReview(spanish: spanish) { data.archive(id, true); archived(id) }
        case .manageAccounts(let editing):
            CuadraoAccountsCollection(data: data, spanish: spanish, editing: editing)
        case .archived:
            CuadraoArchivedAccounts(data: data, spanish: spanish)
        case .rename(let id):
            if let account = data.account(id) { CuadraoRenameAccount(data: data, account: account, spanish: spanish) }
        case .record(let id):
            if let account = data.account(id) { CuadraoTransactionCanvas(data: data, account: account, spanish: spanish) }
        }
    }
}
