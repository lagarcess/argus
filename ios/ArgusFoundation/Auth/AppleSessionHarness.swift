#if DEBUG
import ArgusSession
import AuthenticationServices
import SwiftUI
import Security

/// Synthetic loopback transport exercises the SDK and production recovery screens.
struct AppleSessionHarness: View {
    private static var didReset = false
    @StateObject private var model: ProfileAuthModel
    @State private var checker: HarnessAppleChecker
    @State private var checks = 0

    init() {
        if !Self.didReset && ProcessInfo.processInfo.arguments.contains("--reset-apple-session-harness") {
            Self.didReset = true
            SecItemDelete([kSecClass: kSecClassGenericPassword,
                           kSecAttrService: "local.cuadrao.apple-session-harness"] as CFDictionary)
        }
        let checker = HarnessAppleChecker()
        _checker = State(initialValue: checker)
        let origin = URL(string: "http://127.0.0.1:59920")!
        let config = try! SessionConfiguration(argusAPIURL: origin, supabaseURL: origin,
            publicAnonKey: "sb_publishable_synthetic", keychainService: "local.cuadrao.apple-session-harness")
        let controller = try! SessionController(configuration: config, appleChecker: checker)
        _model = StateObject(wrappedValue: ProfileAuthModel(
            configuration: .init(session: config, webURL: origin, captchaURL: origin), controller: controller))
    }

    var body: some View {
        VStack(spacing: 8) {
            Text("Synthetic Apple session proof").font(.caption)
            Text("Checks: \(checks)").accessibilityIdentifier("harness.checks")
            HStack {
                Button("Apple") { Task {
                    _ = await model.signIn(with: .init(provider: .apple, idToken: "a.b.c", nonce: SignInNonce()), appleAuthorizationCode: "synthetic-code")
                    checks = await checker.count
                } }.accessibilityIdentifier("harness.apple")
                Button("Email") { Task {
                    await model.authenticate(email: "synthetic@example.test", password: "synthetic", captchaToken: "synthetic", signup: false, language: "en", displayName: "")
                } }.accessibilityIdentifier("harness.email")
                Button("Check") { Task { await model.restore(); checks = await checker.count } }
                    .accessibilityIdentifier("harness.check")
            }.buttonStyle(.bordered).disabled(model.busy)
            HStack {
                Button("Authorized") { Task { await checker.set(.authorized) } }.accessibilityIdentifier("harness.authorized")
                Button("Error") { Task { await checker.set(nil) } }.accessibilityIdentifier("harness.error")
                Button("Revoked") { Task { await checker.set(.revoked) } }.accessibilityIdentifier("harness.revoked")
                Button("Transferred") { Task { await checker.set(.transferred) } }.accessibilityIdentifier("harness.transferred")
            }.font(.caption)
            HStack {
                Button("Link") { Task { await setLinkedIdentity(true) } }.accessibilityIdentifier("harness.link")
                Button("No link") { Task { await setLinkedIdentity(false) } }.accessibilityIdentifier("harness.unlink")
                Button("Notify twice") {
                NotificationCenter.default.post(name: ASAuthorizationAppleIDProvider.credentialRevokedNotification, object: nil)
                NotificationCenter.default.post(name: ASAuthorizationAppleIDProvider.credentialRevokedNotification, object: nil)
                }.accessibilityIdentifier("harness.notify")
            }
            HStack {
                Button("Hold check") { Task {
                    await checker.holdNext()
                    await model.restore()
                    checks = await checker.count
                } }.accessibilityIdentifier("harness.hold-check").disabled(model.busy)
                Button("Revoke + notify") { Task {
                    await checker.set(.revoked)
                    NotificationCenter.default.post(name: ASAuthorizationAppleIDProvider.credentialRevokedNotification, object: nil)
                } }.accessibilityIdentifier("harness.revoke-notify")
                Button("Release") { Task { await checker.release() } }.accessibilityIdentifier("harness.release")
            }.font(.caption)
            Divider()
            if model.state == .credentialValidationRequired || model.state == .reauthenticationRequired || model.state == .pendingSignOut {
                ConnectedCuadraoAuthFlow().environmentObject(model)
            } else {
                ScrollView { ProfileAccountSection(model: model).padding(24) }
            }
        }
        .modifier(SessionLifecycle(model: model))
        .alert("auth.apple.capture.title", isPresented: $model.captureNoticePresented) {
            Button("auth.apple.capture.dismiss", role: .cancel) { }
        } message: { if let key = model.captureNoticeKey { Text(LocalizedStringKey(key)) } }
    }

    private func setLinkedIdentity(_ present: Bool) async {
        let path = present ? "identity-present" : "identity-missing"
        _ = try? await URLSession.shared.data(from: URL(string: "http://127.0.0.1:59920/synthetic/" + path)!)
    }
}

private actor HarnessAppleChecker: AppleCredentialChecking {
    var count = 0
    private var answer: AppleCredentialState? = .authorized
    private var hold = false
    private var continuation: CheckedContinuation<Void, Never>?
    func holdNext() { hold = true }
    func release() { continuation?.resume(); continuation = nil }
    func set(_ answer: AppleCredentialState?) { self.answer = answer }
    func state(for subject: String) async throws -> AppleCredentialState {
        count += 1
        let result = answer
        if hold {
            hold = false
            await withCheckedContinuation { continuation = $0 }
        }
        guard let result else { throw SessionFailure.unavailable }
        return result
    }
}
#endif
