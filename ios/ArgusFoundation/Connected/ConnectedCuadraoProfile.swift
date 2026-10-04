import SwiftUI

enum CuadraoProfileDestination: Hashable { case appearance, legal }

struct ConnectedCuadraoProfile: View {
    @Binding var appearance: AppearancePreference
    @Binding var avatar: CuadraoAvatarSelection
    @EnvironmentObject private var auth: ProfileAuthModel
    @Environment(\.locale) private var locale
    @State private var editingAvatar = false
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                Button { editingAvatar = true } label: {
                    HStack(spacing: 18) {
                        CuadraoIdentityAvatar(selection: avatar, name: auth.profile?.displayName ?? "", size: 64)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(auth.profile?.displayName ?? (spanish ? "Tu perfil" : "Your profile"))
                                .font(.title2.weight(.semibold)).foregroundStyle(.primary)
                            Text(spanish ? "Editar avatar" : "Edit avatar").font(CuadraoTypography.supporting)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary)
                    }.contentShape(Rectangle())
                }.buttonStyle(.plain).accessibilityIdentifier("release.profile.avatar")
                VStack(spacing: 0) {
                    NavigationLink(value: CuadraoProfileDestination.appearance) {
                        row(spanish ? "Apariencia" : "Appearance", symbol: "paintpalette")
                    }
                    Divider()
                    NavigationLink(value: CuadraoProfileDestination.legal) {
                        row(spanish ? "Privacidad y términos" : "Privacy and terms", symbol: "hand.raised")
                    }.accessibilityIdentifier("release.profile.legal")
                    if let invitations = auth.invitations { InvitationsProfileRow(model: invitations) }
                }.padding(.horizontal, 16).background(Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 20))
                if auth.enabled { ProfileAccountSection(model: auth) }
            }.padding(24)
        }
        .background(Color(uiColor: .systemGroupedBackground))
        .navigationTitle("").toolbar(.hidden, for: .navigationBar)
        .sheet(isPresented: $editingAvatar) {
            CuadraoIdentityEditor(name: auth.profile?.displayName ?? "", selection: $avatar)
        }
        .navigationDestination(for: CuadraoProfileDestination.self) { destination in
            switch destination {
            case .appearance: AppearancePreferencesView(appearance: $appearance).toolbar(.visible, for: .navigationBar)
            case .legal: CuadraoLegalLinks(webURL: auth.configuration?.webURL)
            }
        }
    }

    private func row(_ title: String, symbol: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: symbol).frame(width: 24)
            Text(title).foregroundStyle(.primary)
            Spacer()
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary)
        }.frame(minHeight: 58).contentShape(Rectangle())
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
