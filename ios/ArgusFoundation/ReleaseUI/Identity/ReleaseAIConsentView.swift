import SwiftUI

public struct ReleaseAIConsentView: View {
    public let disclosure: ReleaseAIConsentDisclosure
    public let state: ReleaseAIConsentState
    public let onAllow: () -> Void
    public let onDecline: () -> Void
    public let onContinue: () -> Void
    @Environment(\.locale) private var locale

    public init(disclosure: ReleaseAIConsentDisclosure, state: ReleaseAIConsentState,
                onAllow: @escaping () -> Void, onDecline: @escaping () -> Void,
                onContinue: @escaping () -> Void) {
        self.disclosure = disclosure; self.state = state
        self.onAllow = onAllow; self.onDecline = onDecline; self.onContinue = onContinue
    }

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private func text(_ es: String, _ en: String) -> String { spanish ? es : en }

    public var body: some View {
        List {
            Section {
                Text(text("Antes de usar IA", "Before using AI"))
                    .font(CuadraoTypography.feature).accessibilityAddTraits(.isHeader)
                Text(disclosure.purpose)
                Text(text("Con tu permiso, enviaremos estos datos a \(disclosure.providerName):",
                          "With your permission, we will send this data to \(disclosure.providerName):"))
                ForEach(Array(disclosure.dataItems.enumerated()), id: \.offset) { _, item in
                    Label(item, systemImage: "doc.text").font(CuadraoTypography.supporting)
                }
                Link(text("Privacidad de \(disclosure.providerName)", "\(disclosure.providerName) privacy"),
                     destination: disclosure.privacyURL)
                    .frame(minHeight: 44).accessibilityIdentifier("identity.ai.privacy")
            }
            Section {
                if state == .accepted {
                    Label(text("Permiso guardado", "Permission saved"), systemImage: "checkmark.circle")
                    Button(text("Continuar", "Continue"), action: onContinue)
                        .accessibilityIdentifier("identity.ai.continue")
                } else {
                    if state == .failed {
                        Label(text("No se pudo guardar tu permiso. Inténtalo otra vez.",
                                   "Your permission couldn't be saved. Try again."), systemImage: "exclamationmark.circle")
                    }
                    if state == .submitting { ProgressView(text("Guardando…", "Saving…")) }
                    Button(text("Permitir y continuar", "Allow and continue"), action: onAllow)
                        .disabled(state == .submitting).accessibilityIdentifier("identity.ai.allow")
                    Button(text("Ahora no", "Not now"), action: onDecline)
                        .disabled(state == .submitting).accessibilityIdentifier("identity.ai.decline")
                }
            }
        }
        .font(CuadraoTypography.body).tint(WelcomePalette.pine)
        .navigationTitle(text("Permiso para IA", "AI permission"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("identity.ai.screen")
    }
}
