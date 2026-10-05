import SwiftUI

struct ConnectedCuadraoProfile: View {
    @Binding var appearance: AppearancePreference
    @Binding var avatar: CuadraoAvatarSelection
    @Binding var path: [CanvasProfileRoute]
    var bottomSpace: CGFloat = 88
    @EnvironmentObject private var auth: ProfileAuthModel
    @Environment(\.locale) private var locale
    @State private var editingAvatar = false
    @State private var settingsExamples = CuadraoProfileSettingsDraft()
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private var displayName: String { auth.profile?.displayName ?? (spanish ? "Tu perfil" : "Your profile") }

    var body: some View {
        NavigationStack(path: $path) {
            CuadraoProfileBody(spanish: spanish,
                identity: .init(name: displayName, emailAddress: auth.profile?.email, avatar: avatar),
                bottomSpace: bottomSpace,
                editProfile: CuadraoFirstRelease.editsAvatar ? { editingAvatar = true } : nil) {
                if let invitations = auth.invitations { ConnectedProfileInvitationsRow(model: invitations) }
            } accountActions: {
                if auth.enabled { ProfileAccountSection(model: auth) }
            }
            .navigationDestination(for: CanvasProfileRoute.self) { route in
                if route == .invitations, let invitations = auth.invitations {
                    InvitationsHub(model: invitations).toolbar(.visible, for: .navigationBar)
                } else {
                    CuadraoProfilePage(route: route, settings: $settingsExamples, spanish: spanish,
                        includeExamples: true, connection: .connected(appearance: $appearance, webURL: auth.configuration?.webURL))
                }
            }
            .sheet(isPresented: $editingAvatar) {
                NavigationStack {
                    CuadraoProfileEditor(name: .constant(displayName), preferredName: .constant(""),
                        emailAddress: auth.profile?.email, avatar: $avatar, spanish: spanish, allowsIdentityEdits: false)
                }.tint(WelcomePalette.pine).preferredColorScheme(appearance.colorScheme)
            }
        }
        .toolbar(.hidden, for: .tabBar)
        .onChange(of: auth.profile?.id) { _, _ in
            settingsExamples = CuadraoProfileSettingsDraft()
            editingAvatar = false
        }
    }
}

private struct ConnectedProfileInvitationsRow: View {
    @ObservedObject var model: InvitationsModel
    @Environment(\.locale) private var locale

    var body: some View {
        if model.showsInvitations {
            Rectangle().fill(CanvasSettingsStyle.separator).frame(height: 0.5)
                .padding(.leading, 54).padding(.trailing, 18).accessibilityHidden(true)
            NavigationLink(value: CanvasProfileRoute.invitations) {
                CanvasProfileRow(route: .invitations, spanish: locale.language.languageCode?.identifier == "es")
            }.buttonStyle(.plain).accessibilityIdentifier("invites.profile")
        }
    }
}

struct CuadraoLegalLinks: View {
    let webURL: URL?
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        List {
            if let webURL {
                Link(destination: webURL.appendingPathComponent("privacy")) {
                    Label(spanish ? "Privacidad" : "Privacy", systemImage: "hand.raised")
                }.accessibilityIdentifier("release.legal.privacy")
                Link(destination: webURL.appendingPathComponent("terms")) {
                    Label(spanish ? "Términos de uso" : "Terms of use", systemImage: "doc.text")
                }.accessibilityIdentifier("release.legal.terms")
            } else {
                Text(spanish ? "Los enlaces no están disponibles en este momento." : "These links aren’t available right now.")
            }
        }.navigationTitle(spanish ? "Privacidad y términos" : "Privacy and terms")
            .navigationBarTitleDisplayMode(.inline).toolbar(.visible, for: .navigationBar)
    }
}
