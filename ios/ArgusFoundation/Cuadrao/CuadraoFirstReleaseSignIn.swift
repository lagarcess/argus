import Foundation

extension CuadraoFirstRelease {
    /// Apple and Google sign-in stay hidden in the preview until the founder's choice and the
    /// connected path are both settled (#787, Authentication). The preview's Apple control and
    /// its recovery copy stay in code behind this switch.
    static let showsSocialSignIn = false
}
