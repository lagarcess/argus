import SwiftUI

/// Shared account actions for Home, Search and insights navigation.
enum CanvasAccountSheet: Identifiable {
    case actions(UUID), rename(UUID), record(UUID)
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
        case .actions(let id):
            if let account = data.account(id) {
                CuadraoAccountActions(account: account, spanish: spanish,
                    rename: { show(.rename(id)) }, record: { show(.record(id)) }, archive: {
                        data.archive(id, true); archived(id)
                    })
            }
        case .rename(let id):
            if let account = data.account(id) { CuadraoRenameAccount(data: data, account: account, spanish: spanish) }
        case .record(let id):
            if let account = data.account(id) { CuadraoTransactionCanvas(data: data, account: account, spanish: spanish) }
        }
    }
}
