import AuthenticationServices
import SwiftUI

/// Connects the shared deletion screen to the session owner's command. Consequences stay general until the
/// server resolves household successors and shared plans for this person.
struct ConnectedAccountDeletion: View {
    @ObservedObject var model: AccountDeletionModel
    @EnvironmentObject private var auth: ProfileAuthModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ReleaseDeleteAccountView(consequences: .init(), state: model.state,
            onSubmit: { _ in Task { await model.submit() } },
            onRetry: { Task { await model.retry() } },
            onComplete: { model.finish(); dismiss() },
            appleAuthorization: auth.providers.apple ? AnyView(appleAuthorization) : nil)
            .navigationBarBackButtonHidden(model.state == .submitting)
    }

    private var appleAuthorization: some View {
        AppleAuthorizationButton(busy: model.state == .submitting) { request in
            request.requestedScopes = []
        } onCompletion: { result in
            guard case .success(let authorization) = result,
                  let code = (authorization.credential as? ASAuthorizationAppleIDCredential)?.authorizationCodeText else { return }
            Task { await model.submit(appleAuthorizationCode: code) }
        }
        .accessibilityIdentifier("identity.delete.appleAuthorize")
    }
}

/// The signed-out destination keeps an unresolved, accepted or confirmed deletion in front of sign-in.
struct ConnectedDeletionOutcome<Content: View>: View {
    @ObservedObject var model: AccountDeletionModel
    let unresolved: Bool
    @ViewBuilder let content: Content

    var body: some View {
        if unresolved || model.presentsOutcome {
            ConnectedAccountDeletion(model: model)
                .task(id: unresolved) { if unresolved { await model.load() } }
        } else {
            content
        }
    }
}
