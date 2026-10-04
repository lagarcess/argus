import SwiftUI
import ArgusSession

/// Why a Household invitation could not be previewed or accepted. Membership never changes here.
struct HouseholdInvitationProblemText: View {
    let problem: InvitationProblem
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        Label(message, systemImage: "info.circle")
            .font(.footnote)
            .accessibilityIdentifier("household.invite.problem." + identifier)
    }

    private var identifier: String {
        switch problem {
        case .invalid: "invalid"
        case .expired: "expired"
        case .revoked: "revoked"
        case .used: "used"
        case .rateLimited: "rateLimited"
        default: "unavailable"
        }
    }

    private var message: String {
        switch problem {
        case .invalid:
            spanish ? "No reconocemos ese enlace o código. Revísalo e intenta de nuevo." : "We don't recognize that link or code. Check it and try again."
        case .expired:
            spanish ? "Esta invitación al Hogar venció. Pide una nueva a quien administra el Hogar." : "This Household invitation expired. Ask the Household admin for a new one."
        case .revoked:
            spanish ? "Esta invitación al Hogar ya no está disponible. Pide una nueva." : "This Household invitation is no longer available. Ask for a new one."
        case .used:
            spanish ? "Esta invitación al Hogar ya fue utilizada. Pide una nueva." : "This Household invitation has already been used. Ask for a new one."
        case .rateLimited:
            spanish ? "Hiciste muchos intentos. Espera unos minutos y vuelve a intentarlo." : "You've made too many attempts. Wait a few minutes and try again."
        default:
            spanish ? "No pudimos revisar la invitación. Intenta de nuevo más tarde." : "We couldn't check the invitation. Try again later."
        }
    }
}

struct HouseholdInvitationEntryHint: View {
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        Text(spanish ? "Pega el enlace o escribe el código de la invitación." : "Paste the invitation link or type its code.")
            .font(.caption).foregroundStyle(.secondary)
            .accessibilityIdentifier("household.invite.hint")
    }
}
