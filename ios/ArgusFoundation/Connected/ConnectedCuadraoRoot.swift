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
                ConnectedCuadraoShell(appearance: $appearance)
            case .signedOut, .configurationInvalid, .pendingSignOut, .unsupportedAnonymous:
                ConnectedCuadraoAuthFlow()
            }
        }
    }
}
