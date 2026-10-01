import SwiftUI
import UIKit

struct CanvasHouseholdInvitation: Identifiable {
    let id = UUID()
    // Reserved non-resolving domain: the native sheet never exposes a real invitation.
    var url: URL { URL(string: "https://cuadrao.invalid/invite/\(id.uuidString)")! }
}

struct CuadraoInvitationShareSheet: UIViewControllerRepresentable {
    let invitation: CanvasHouseholdInvitation
    let spanish: Bool

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let message = spanish ? "Te invito a Hogar en Cuadrao. Vista previa: este enlace es de ejemplo."
            : "Join my household in Cuadrao. Design preview: this is a sample link."
        // Sharing completion is not evidence of delivery, recipient identity or acceptance.
        return UIActivityViewController(activityItems: [message, invitation.url], applicationActivities: nil)
    }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}

struct CuadraoInvitationRecipient: View {
    let data: CuadraoAccountsPreview
    let invitation: CanvasHouseholdInvitation
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var accepted = false
    private var available: Bool {
        if case .invitation(let current) = data.household { return current.id == invitation.id }
        return false
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                Image(systemName: accepted ? "checkmark" : "person.2")
                    .font(.system(size: 28, weight: .light)).foregroundStyle(WelcomePalette.pine)
                    .frame(width: 60, height: 60)
                    .background(WelcomePalette.sage, in: RoundedRectangle(cornerRadius: 18)).accessibilityHidden(true)
                if accepted {
                    RegistrationHeading(title: spanish ? "Ya eres parte\ndel hogar." : "You're part of\nthe household.",
                        detail: spanish ? "Tus cuentas personales siguen siendo privadas. En Hogar verás solo lo que compartan."
                            : "Your personal accounts stay private. Household shows only what you share.")
                    RegistrationButton(title: spanish ? "Continuar" : "Continue") { dismiss() }
                } else if available {
                    RegistrationHeading(title: spanish ? "Te invitaron\na Hogar." : "You're invited\nto Household.",
                        detail: spanish ? "Un espacio para llevar juntos las cuentas que comparten."
                            : "A space to manage the accounts you share, together.")
                    VStack(alignment: .leading, spacing: 20) {
                        Label(spanish ? "Solo verás lo compartido" : "You'll see only what's shared", systemImage: "person.2")
                        Label(spanish ? "Tus cuentas personales siguen privadas" : "Your personal accounts stay private", systemImage: "lock")
                    }.font(.subheadline).fixedSize(horizontal: false, vertical: true)
                    RegistrationButton(title: spanish ? "Aceptar invitación" : "Accept invitation") {
                        guard available else { return }
                        data.household = .joined("Alex")
                        accepted = true
                    }.accessibilityIdentifier("household-accept-invitation")
                    Button(spanish ? "Ahora no" : "Not now") { dismiss() }
                        .frame(maxWidth: .infinity, minHeight: 44)
                } else {
                    RegistrationHeading(title: spanish ? "Esta invitación\nya no está disponible." : "This invitation\nis no longer available.",
                        detail: spanish ? "Pide a quien te invitó que comparta un enlace nuevo." : "Ask the person who invited you for a new link.")
                    RegistrationButton(title: spanish ? "Volver" : "Go back") { dismiss() }
                }
            }.padding(24)
        }.background(Color.white)
            .navigationTitle(spanish ? "Vista del invitado" : "Recipient preview")
            .navigationBarTitleDisplayMode(.inline)
    }
}
