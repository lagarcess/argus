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
        VStack(alignment: .leading, spacing: 28) {
            Image(systemName: shared ? "person.2" : "wallet.bifold")
                .font(.system(size: 28, weight: .light)).foregroundStyle(WelcomePalette.pine)
                .frame(width: 60, height: 60)
                .background(WelcomePalette.sage, in: RoundedRectangle(cornerRadius: 18))
                .accessibilityHidden(true)
            RegistrationHeading(title: title, detail: detail)
            if shared {
                RegistrationButton(title: spanish ? "Añadir cuenta conjunta" : "Add a joint account", action: addAccount)
                if case .alone = data.household {
                    secondary(spanish ? "Invitar a alguien" : "Invite someone", action: household)
                } else {
                    secondary(spanish ? "Personas" : "People", action: household)
                }
            } else {
                RegistrationButton(title: spanish ? "Añadir cuenta" : "Add account", action: addAccount)
            }
        }.padding(.top, 16).frame(maxWidth: .infinity, alignment: .leading)
    }
    private func secondary(_ title: String, action: @escaping () -> Void) -> some View {
        Button(title, action: action).font(.subheadline.weight(.medium))
            .frame(maxWidth: .infinity, minHeight: 44)
    }
    private var title: String {
        guard shared else { return spanish ? "Empieza con una cuenta." : "Start with one account." }
        return spanish ? "Un lugar para\nlo de ustedes." : "A place for\nwhat you share."
    }
    private var detail: String {
        guard shared else {
            return spanish ? "Tu banco, tu efectivo o tus ahorros. Tú eliges por dónde empezar."
                : "Your bank, cash or savings. Choose where to begin."
        }
        return spanish ? "Añade una cuenta que lleven juntos. Las cuentas personales siguen siendo privadas."
            : "Add an account you manage together. Personal accounts stay private."
    }
}
