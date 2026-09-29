import SwiftUI
import ArgusSession

@MainActor
final class ProfileAuthModel: ObservableObject {
    enum State { case disabled, configurationInvalid, signedOut, authenticated, pendingSignOut, unsupportedAnonymous }
    @Published private(set) var state: State = .disabled
    @Published private(set) var busy = false
    @Published private(set) var profile: SessionProfile?
    @Published private(set) var confirmationRequired = false
    @Published private(set) var errorKey: String?
    @Published private(set) var accounts: AccountsModel?
    @Published private(set) var financialLoop: FinancialLoopModel?
    let configuration: NativeAuthConfiguration?
    private let controller: SessionController?
    private var started = false

    init() {
        var loadedConfiguration: NativeAuthConfiguration?
        var loadedController: SessionController?
        var initialState = State.disabled
        do {
            loadedConfiguration = try NativeAuthConfiguration.load()
            if let loadedConfiguration {
                loadedController = try SessionController(configuration: loadedConfiguration.session)
                initialState = .signedOut
            }
        } catch {
            loadedConfiguration = nil
            initialState = .configurationInvalid
        }
        configuration = loadedConfiguration
        controller = loadedController
        state = initialState
        if let loadedController {
            accounts = AccountsModel(controller: loadedController)
            accounts?.sessionChanged = { [weak self] snapshot in self?.accept(snapshot) }
            if let accounts {
                financialLoop = FinancialLoopModel(controller: loadedController, accounts: accounts)
                financialLoop?.sessionChanged = { [weak self] snapshot in self?.accept(snapshot) }
            }
        }
    }

    var enabled: Bool { state != .disabled }

    func start() async {
        guard !started else { return }
        started = true
        await restore()
    }

    func restore() async {
        guard let controller, !busy else { return }
        await perform {
            if state == .authenticated { return try await controller.profile() }
            return try await controller.restore()
        }
    }

    func authenticate(email: String, password: String, captchaToken: String, signup: Bool, language: String, displayName: String) async {
        guard let controller, !busy, state == .signedOut else { return }
        busy = true
        errorKey = nil
        confirmationRequired = false
        defer { busy = false }
        do {
            if signup {
                let outcome = try await controller.signup(email: email, password: password, captchaToken: captchaToken,
                                                          language: language, displayName: displayName.isEmpty ? nil : displayName)
                switch outcome {
                case .confirmationRequired:
                    confirmationRequired = true
                    accept(await controller.snapshot())
                case .authenticated(let snapshot): accept(snapshot)
                }
            } else {
                accept(try await controller.login(email: email, password: password, captchaToken: captchaToken))
            }
        } catch {
            accept(await controller.snapshot())
            errorKey = Self.messageKey(error)
        }
    }

    func signOut() async {
        guard let controller else { return }
        accounts?.bind(nil)
        financialLoop?.bind(nil)
        await perform { try await controller.signOut() }
    }

    func retryPendingSignOut() async {
        guard let controller else { return }
        await perform { try await controller.retryPendingSignOut() }
    }

    func returnToSignIn() {
        confirmationRequired = false
        errorKey = nil
    }

    func presentationError(_ key: String) { errorKey = key }

    private func perform(_ action: () async throws -> SessionSnapshot) async {
        guard !busy else { return }
        busy = true
        errorKey = nil
        defer { busy = false }
        do { accept(try await action()) }
        catch {
            if let controller { accept(await controller.snapshot()) }
            errorKey = Self.messageKey(error)
        }
    }

    private func accept(_ snapshot: SessionSnapshot) {
        accounts?.bind(snapshot)
        financialLoop?.bind(snapshot)
        profile = snapshot.profile
        switch snapshot.phase {
        case .signedOut: state = .signedOut
        case .authenticated: state = .authenticated
        case .signOutPending: state = .pendingSignOut
        case .unsupportedAnonymousSession: state = .unsupportedAnonymous
        }
    }

    private static func messageKey(_ error: Error) -> String {
        guard let failure = error as? SessionFailure else { return "auth.error.unavailable" }
        switch failure {
        case .unauthorized: return "auth.error.unauthorized"
        case .storageUnavailable: return "auth.error.storage"
        case .pendingSignOut: return "auth.error.pending"
        case .unsupportedAnonymousTransfer: return "auth.error.anonymous"
        case .invalidConfiguration: return "auth.error.configuration"
        case .rejected(let status, _):
            return status == 429 ? "auth.error.rateLimit" : "auth.error.rejected"
        default: return "auth.error.unavailable"
        }
    }
}
