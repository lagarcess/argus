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
                switch data.household {
                case .alone:
                    RegistrationButton(title: spanish ? "Invitar a alguien" : "Invite someone", action: household)
                    secondary(spanish ? "Añadir cuenta conjunta" : "Add a joint account", action: addAccount)
                case .invitation:
                    VStack(alignment: .leading, spacing: 8) {
                        Label(spanish ? "Enlace de invitación" : "Invitation link", systemImage: "link")
                        Text(spanish ? "Nadie se ha unido todavía" : "No one has joined yet").font(.subheadline).foregroundStyle(.secondary)
                        Button(spanish ? "Ver invitación" : "View invitation", action: household).frame(minHeight: 44)
                    }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
                        .background(WelcomePalette.sage, in: RoundedRectangle(cornerRadius: 18))
                    secondary(spanish ? "Añadir cuenta conjunta" : "Add a joint account", action: addAccount)
                case .joined(let name):
                    Label(spanish ? "Tú y \(name)" : "You and \(name)", systemImage: "person.2")
                        .font(.subheadline).foregroundStyle(.secondary)
                    RegistrationButton(title: spanish ? "Añadir cuenta conjunta" : "Add a joint account", action: addAccount)
                    secondary(spanish ? "Ver personas" : "View people", action: household)
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
        switch data.household {
        case .alone: return spanish ? "Un lugar para\nlo de ustedes." : "A place for\nwhat you share."
        case .invitation: return spanish ? "Tu hogar ya\ntiene su espacio." : "Your household\nhas a home here."
        case .joined: return spanish ? "Ya están aquí.\nAhora, lo compartido." : "You're both here.\nNow, what you share."
        }
    }
    private var detail: String {
        guard shared else {
            return spanish ? "Tu banco, tu efectivo o tus ahorros. Tú eliges por dónde empezar."
                : "Your bank, cash or savings. Choose where to begin."
        }
        switch data.household {
        case .alone: return spanish ? "Invita a quien comparte contigo. Tus cuentas personales siguen siendo privadas."
            : "Invite someone you share with. Your personal accounts stay private."
        case .invitation: return spanish ? "Comparte el enlace cuando quieras. También puedes empezar con una cuenta conjunta."
            : "Share the link when you’re ready. You can also start with a joint account."
        case .joined: return spanish ? "Todavía no hay cuentas compartidas. Unirse al hogar no comparte las cuentas personales."
            : "There are no shared accounts yet. Joining a household doesn't share personal accounts."
        }
    }
}
