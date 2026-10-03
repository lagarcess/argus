import SwiftUI

struct CuadraoEmailConfirmation: View {
    let spanish: Bool
    let email: String
    @Environment(\.dismiss) private var dismiss
    @State private var showingHelp = false

    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Image(systemName: "envelope.badge.shield.half.filled")
                        .font(.system(size: 32, weight: .light))
                        .foregroundStyle(WelcomePalette.pine)
                        .frame(width: 72, height: 72)
                        .background(WelcomePalette.sage, in: RoundedRectangle(cornerRadius: 22))
                        .accessibilityHidden(true)
                        .padding(.bottom, 28)
                    RegistrationHeading(
                        title: spanish ? "Confirma tu correo." : "Confirm your email.",
                        detail: spanish ? "Abre el enlace de confirmación en:" : "Open the confirmation link at:")
                    Text(email)
                        .font(.body.weight(.semibold))
                        .textSelection(.enabled)
                        .padding(.top, 10)
                    Button(spanish ? "Cambiar correo" : "Change email") { dismiss() }
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(WelcomePalette.pine)
                        .frame(minHeight: 44)
                        .padding(.top, 6)
                    Spacer(minLength: 40)
                    Text(spanish ? "Después, vuelve a Cuadrao para iniciar sesión."
                         : "Then return to Cuadrao to sign in.")
                        .font(.body).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.bottom, 24)
                    NavigationLink {
                        CuadraoEmailSignIn(spanish: spanish, initialEmail: email)
                    } label: {
                        Text(spanish ? "Ir a iniciar sesión" : "Go to sign in")
                            .font(.body.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 56)
                            .foregroundStyle(WelcomePalette.onAccent)
                            .background(WelcomePalette.pine, in: RoundedRectangle(cornerRadius: 16))
                    }.buttonStyle(.plain)
                    Button(spanish ? "¿No encuentras el correo?" : "Can’t find the email?") {
                        showingHelp.toggle()
                    }
                    .font(.subheadline)
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .padding(.top, 8)
                    if showingHelp {
                        Text(spanish ? "Revisa la carpeta de correo no deseado y comprueba que la dirección esté bien escrita."
                             : "Check your spam folder and make sure the email address is correct.")
                            .font(.footnote).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, 8)
                    }
                }
                .padding(.horizontal, 28)
                .padding(.top, 24)
                .padding(.bottom, 20)
                .frame(minHeight: geometry.size.height, alignment: .topLeading)
            }
        }
        .background(WelcomePalette.background.ignoresSafeArea())
        .foregroundStyle(WelcomePalette.ink)
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)

    }
}

#Preview("Email · Confirmation") {
    NavigationStack { CuadraoEmailConfirmation(spanish: true, email: "alex@example.com") }
}
