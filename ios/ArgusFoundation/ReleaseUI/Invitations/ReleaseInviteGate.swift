import SwiftUI

enum ReleaseInviteGateState: String, CaseIterable {
    case ready, checking, invalid, expired, full, waitlist, consumed, revoked, rateLimited, unavailable

    func title(spanish: Bool) -> String {
        switch self {
        case .ready: spanish ? "Escribir código" : "Enter code"
        case .checking: spanish ? "Comprobando" : "Checking"
        case .invalid: spanish ? "Código inválido" : "Invalid code"
        case .expired: spanish ? "Invitación vencida" : "Expired invitation"
        case .full: spanish ? "Enlace lleno" : "Full link"
        case .waitlist: spanish ? "Lista de espera" : "Waitlist"
        case .consumed: spanish ? "Invitación utilizada" : "Used invitation"
        case .revoked: spanish ? "Invitación revocada" : "Revoked invitation"
        case .rateLimited: spanish ? "Demasiados intentos" : "Too many attempts"
        case .unavailable: spanish ? "No disponible" : "Unavailable"
        }
    }

    func message(spanish: Bool) -> String? {
        switch self {
        case .ready, .checking: nil
        case .invalid: spanish ? "No reconocemos ese código. Revísalo e intenta de nuevo." : "We don't recognize that code. Check it and try again."
        case .expired: spanish ? "Esta invitación venció. Pide otra o visita la lista de espera." : "This invitation expired. Ask for another or visit the waitlist."
        case .full: spanish ? "Este enlace alcanzó su límite. Puedes unirte a la lista de espera en cuadrao.ai." : "This link has reached its limit. You can join the waitlist at cuadrao.ai."
        case .waitlist: spanish ? "Necesitas una invitación para entrar. Puedes unirte a la lista de espera en cuadrao.ai." : "You need an invitation to enter. You can join the waitlist at cuadrao.ai."
        case .consumed: spanish ? "Esta invitación ya fue utilizada. Pide una nueva." : "This invitation has already been used. Ask for a new one."
        case .revoked: spanish ? "Esta invitación ya no está disponible. Pide una nueva." : "This invitation is no longer available. Ask for a new one."
        case .rateLimited: spanish ? "Hiciste muchos intentos. Espera unos minutos y vuelve a intentarlo." : "You've made too many attempts. Wait a few minutes and try again."
        case .unavailable: spanish ? "No pudimos comprobar tu invitación. Intenta de nuevo más tarde." : "We couldn't check your invitation. Try again later."
        }
    }
}

struct ReleaseInviteGate: View {
    let state: ReleaseInviteGateState
    @Binding var code: String
    let spanish: Bool
    let onSubmit: (String) -> Void
    let onWaitlist: () -> Void
    var showsWaitlist = true

    var body: some View {
        ReleaseInvitationPage(title: spanish ? "Tu invitación\na Cuadrao." : "Your invitation\nto Cuadrao.",
                              subtitle: spanish ? "Ya iniciaste sesión. Escribe tu código para entrar a la beta." : "You're signed in. Enter your code to join the beta.") {
            VStack(alignment: .leading, spacing: 16) {
                Text(spanish ? "Código de invitación" : "Invitation code").font(CuadraoTypography.supporting)
                TextField(spanish ? "Escribe tu código" : "Enter your code", text: $code)
                    .font(.system(.title3, design: .monospaced))
                    .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    .submitLabel(.go).padding(16)
                    .background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 16))
                    .disabled(state == .checking)
                    .accessibilityIdentifier("release.inviteGate.code")
                    .onSubmit { submit() }
                if let message = state.message(spanish: spanish) {
                    Label(message, systemImage: "info.circle")
                        .font(CuadraoTypography.supporting)
                        .accessibilityIdentifier("release.inviteGate.status." + state.rawValue)
                }
                Button(action: submit) {
                    HStack {
                        if state == .checking { ProgressView().tint(WelcomePalette.onAccent) }
                        Text(state == .checking ? (spanish ? "Comprobando…" : "Checking…") : (spanish ? "Continuar" : "Continue"))
                    }.frame(maxWidth: .infinity, minHeight: 48)
                }
                .buttonStyle(.borderedProminent)
                .disabled(code.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || state == .checking)
                .accessibilityIdentifier("release.inviteGate.submit")
                Text(spanish ? "TestFlight instala la app. Tu invitación te da acceso a la beta."
                     : "TestFlight installs the app. Your invitation gives you beta access.")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                if showsWaitlist {
                    Button(action: onWaitlist) {
                        Text(spanish ? "No tengo código · Lista de espera" : "No code? Visit the waitlist")
                            .frame(minHeight: 44)
                    }.accessibilityIdentifier("release.inviteGate.waitlist")
                    Text("cuadrao.ai").font(CuadraoTypography.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    private func submit() {
        let value = code.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty, state != .checking else { return }
        onSubmit(value)
    }
}
