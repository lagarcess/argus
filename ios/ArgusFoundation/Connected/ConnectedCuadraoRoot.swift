import SwiftUI

/// Routes between sample FoundationShell, Cuadrao auth, and the connected shell.
struct ConnectedCuadraoRoot: View {
    @Binding var appearance: AppearancePreference
    @EnvironmentObject private var auth: ProfileAuthModel

    var body: some View {
        Group {
            switch auth.state {
            case .disabled:
                FoundationShell(appearance: $appearance)
            case .authenticated:
                if let invitations = auth.invitations {
                    InvitationGateHost(model: invitations, household: auth.household, signOut: { Task { await auth.signOut() } }) {
                        ConnectedCuadraoShell(appearance: $appearance)
                    }
                } else {
                    ConnectedCuadraoShell(appearance: $appearance)
                }
            case .signedOut, .configurationInvalid, .pendingSignOut, .unsupportedAnonymous:
                ConnectedCuadraoAuthFlow()
                    .safeAreaInset(edge: .top) { if let invitations = auth.invitations { InvitationPendingNotice(model: invitations) } }
            }
        }
        .invitationLinks(auth.invitations)
        .onAppear { auth.invitations?.openHousehold = { [weak auth] input in await auth?.household?.beginJoin(input) == true } }
    }
}
