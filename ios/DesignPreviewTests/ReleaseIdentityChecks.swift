import Foundation

@main
struct ReleaseIdentityChecks {
    static func main() {
        for value in ["", "delete", "DELETE ME", "123456"] {
            precondition(!ReleaseDeletionVerification.typedDelete.accepts(value), "Deletion needs the exact confirmation word")
        }
        for value in ["DELETE", "  DELETE\n"] {
            precondition(ReleaseDeletionVerification.typedDelete.accepts(value))
        }
        precondition(!ReleaseDeletionVerification.code.accepts(" \n"))
        precondition(ReleaseDeletionVerification.code.accepts("123456"))

        for state in [ReleaseDeletionState.ready, .verificationRejected] {
            precondition(state.allowsVerificationInput)
        }
        for state in [ReleaseDeletionState.verificationResending, .submitting, .pending, .failed, .completed,
                      .appleAuthorizationRequired, .uncertain(canRetry: true), .uncertain(canRetry: false), .supportRequested, .supportUnavailable] {
            precondition(!state.allowsVerificationInput, "Verification cannot change while an operation is pending")
        }

        for provider in ReleaseSocialProvider.allCases {
            precondition(ReleaseSocialSignInState.loading(provider).isBusy)
        }
        precondition(ReleaseSocialSignInState.savingName.isBusy)
        for state in [ReleaseSocialSignInState.idle, .cancelled, .failed, .missingName, .nameFailed, .complete] {
            precondition(!state.isBusy)
        }

        for enabled in [false, true] {
            let updating = ReleaseMemoryState.updating(isEnabled: enabled)
            precondition(updating.isBusy && updating.isEnabled == enabled)
            let resetting = ReleaseMemoryState.resetting(isEnabled: enabled)
            precondition(resetting.isBusy && resetting.isEnabled == enabled)
            let failure = ReleaseMemoryState.failed(isEnabled: enabled)
            precondition(!failure.isBusy && failure.isEnabled == enabled)
            let complete = ReleaseMemoryState.resetComplete(isEnabled: enabled)
            precondition(!complete.isBusy && complete.isEnabled == enabled)
        }
        precondition(!ReleaseMemoryState.off.isEnabled)
        precondition(ReleaseMemoryState.on.isEnabled)
        print("Release identity checks passed")
    }
}
