import SwiftUI

/// One row of the + tray: what it is called, and what choosing it does.
struct CuadraoAddItem: Identifiable {
    let action: CuadraoAddAction
    let perform: () -> Void
    var id: String { action.id }
}

extension CuadraoAddAction {
    func title(spanish: Bool) -> String {
        switch self {
        case .account: spanish ? "Cuenta" : "Account"
        case .transaction: spanish ? "Transacción" : "Transaction"
        case .scan: spanish ? "Escanear o archivo" : "Scan or file"
        case .group: spanish ? "Grupo" : "Group"
        case .plan: "Plan"
        case .invite: spanish ? "Invitar" : "Invite"
        }
    }

    var symbol: String {
        switch self {
        case .account: "creditcard"
        case .transaction: "arrow.left.arrow.right"
        case .scan: "doc.viewfinder"
        case .group: "person.2"
        case .plan: "calendar.badge.plus"
        case .invite: "person.badge.plus"
        }
    }
}

/// The add tray: the chat attachment tray's card, sliding up above the navigation bar.
struct CuadraoAddTray: View {
    let items: [CuadraoAddItem]
    let spanish: Bool
    let choose: (CuadraoAddItem) -> Void

    var body: some View {
        VStack(spacing: 0) {
            ForEach(items) { item in
                Button { choose(item) } label: {
                    HStack(spacing: 14) {
                        Image(systemName: item.action.symbol)
                            .font(.system(size: 19, weight: .regular))
                            .frame(width: 26).foregroundStyle(.secondary)
                        Text(item.action.title(spanish: spanish)).font(.body)
                        Spacer(minLength: 8)
                    }
                    .padding(.horizontal, 6).frame(minHeight: 48).contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("add.tray." + item.action.rawValue)
                if item.id != items.last?.id {
                    Divider().padding(.leading, 46)
                }
            }
        }
        .padding(.vertical, 6).padding(.horizontal, 12)
        .background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 26))
        .padding(.horizontal, 16)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("add.tray")
    }
}
