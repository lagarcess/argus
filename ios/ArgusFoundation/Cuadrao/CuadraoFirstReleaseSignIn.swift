import Foundation

extension CuadraoFirstRelease {
    /// The preview's own Apple control stays hidden. Connected Apple and Google sign-in (decision 18, #795)
    /// is `ConnectedProviderButtons`, gated by ARGUS_APPLE_SIGN_IN_ENABLED and ARGUS_GOOGLE_SIGN_IN_ENABLED.
    static let showsSocialSignIn = false
}
