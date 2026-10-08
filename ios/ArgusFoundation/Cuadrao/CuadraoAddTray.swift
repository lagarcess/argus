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

/// The add tray: the chat attachment tray's card, popping out of the + above the navigation bar.
struct CuadraoAddTray: View {
    let items: [CuadraoAddItem]
    let spanish: Bool
    let choose: (CuadraoAddItem) -> Void
    @ScaledMetric(relativeTo: .body) private var glyphSize: CGFloat = 19
    @AccessibilityFocusState private var focusedRow: String?

    var body: some View {
        ScrollView {
            rows
        }
        .scrollBounceBehavior(.basedOnSize)
        .fixedSize(horizontal: false, vertical: true)
        .frame(maxHeight: 420)
        .padding(.vertical, 6).padding(.horizontal, 12)
        .background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 28))
        .shadow(color: .black.opacity(0.14), radius: 20, y: 6)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("add.tray")
        .onAppear { focusedRow = items.first?.id }
    }

    private var rows: some View {
        VStack(spacing: 0) {
            ForEach(items) { item in
                Button { choose(item) } label: {
                    HStack(spacing: 14) {
                        Image(systemName: item.action.symbol)
                            .font(.system(size: glyphSize, weight: .regular))
                            .frame(width: glyphSize + 7).foregroundStyle(.secondary)
                            .accessibilityHidden(true)
                        Text(item.action.title(spanish: spanish)).font(.body)
                        Spacer(minLength: 8)
                    }
                    .padding(.horizontal, 6).frame(minHeight: 48).contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("add.tray." + item.action.rawValue)
                .accessibilityFocused($focusedRow, equals: item.id)
                if item.id != items.last?.id {
                    Divider().padding(.leading, 46)
                }
            }
        }
    }
}
