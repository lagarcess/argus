import SwiftUI

// In-memory design fixtures. No invitations or membership changes leave this canvas.
enum CanvasHouseholdState {
    case alone, invitation(CanvasHouseholdInvitation), joined(String)
}

struct CuadraoHomeEmptyState: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    let addAccount: () -> Void
    let household: () -> Void
    private var shared: Bool { data.selectedSpace.kind == .household }

    var body: some View {
        if shared {
            VStack(alignment: .leading, spacing: 28) {
                CuadraoChartState(title: spanish ? "Un lugar para\nlo de ustedes." : "A place for\nwhat you share.",
                    detail: spanish ? "Añade una cuenta que lleven juntos. Las cuentas personales siguen siendo privadas."
                        : "Add an account you manage together. Personal accounts stay private.")
                RegistrationButton(title: spanish ? "Añadir cuenta conjunta" : "Add a joint account", action: addAccount)
                if case .alone = data.household {
                    secondary(spanish ? "Invitar a alguien" : "Invite someone", action: household)
                } else {
                    secondary(spanish ? "Personas" : "People", action: household)
                }
            }.padding(.top, 16).frame(maxWidth: .infinity, alignment: .leading)
        } else {
            CuadraoPersonalAccountsEmpty(spanish: spanish, addAccount: addAccount)
        }
    }
    private func secondary(_ title: String, action: @escaping () -> Void) -> some View {
        Button(title, action: action).font(.subheadline.weight(.medium))
            .frame(maxWidth: .infinity, minHeight: 44)
    }
}

struct CuadraoPersonalAccountsEmpty: View {
    let spanish: Bool
    let addAccount: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            CuadraoChartState(title: spanish ? "Empieza con una cuenta." : "Start with one account.",
                detail: spanish ? "Tu banco, tu efectivo o tus ahorros. Tú eliges por dónde empezar."
                    : "Your bank, cash or savings. Choose where to begin.")
            RegistrationButton(title: spanish ? "Añadir cuenta" : "Add account", action: addAccount)
                .accessibilityIdentifier("accounts.add")
        }.padding(.top, 16).frame(maxWidth: .infinity, alignment: .leading)
    }
}
