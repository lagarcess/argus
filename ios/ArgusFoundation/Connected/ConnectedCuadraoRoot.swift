import SwiftUI

/// Routes between sample FoundationShell, Cuadrao auth, and the connected shell.
struct ConnectedCuadraoRoot: View {
    @Binding var appearance: AppearancePreference
    @EnvironmentObject private var auth: ProfileAuthModel

    var body: some View {
        Group {
            switch auth.state {
            case .disabled:
                FoundationShell(appearance: $appearance).modifier(ArgusChrome())
            case .authenticated:
                if let invitations = auth.invitations {
                    InvitationGateHost(model: invitations, household: auth.household, signOut: { Task { await auth.signOut() } }) {
                        ConnectedCuadraoShell(appearance: $appearance)
                    }
                } else {
                    ConnectedCuadraoShell(appearance: $appearance)
                }
            case .accountDeletionUncertain, .accountDeletionPending, .signedOut, .configurationInvalid, .pendingSignOut, .unsupportedAnonymous, .credentialValidationRequired, .reauthenticationRequired:
                ConnectedCuadraoAuthFlow()
                    .safeAreaInset(edge: .top) { if let invitations = auth.invitations { InvitationPendingNotice(model: invitations) } }
                    .modifier(ArgusChrome())
            }
        }
        .alert("auth.apple.capture.title", isPresented: $auth.captureNoticePresented) {
            Button("auth.apple.capture.dismiss", role: .cancel) { }
        } message: {
            if let key = auth.captureNoticeKey { Text(LocalizedStringKey(key)) }
        }
        .invitationLinks(auth.invitations)
        .onAppear { auth.invitations?.openHousehold = { [weak auth] input in await auth?.household?.beginJoin(input) == true } }
    }
}

/// The sample shell and the auth flow keep the Argus tokens; the signed-in Cuadrao shell inherits nothing, like the Preview.
private struct ArgusChrome: ViewModifier {
    func body(content: Content) -> some View {
        content.tint(ArgusStyle.ink).foregroundStyle(ArgusStyle.ink).font(ArgusStyle.body())
    }
}
