import Foundation

@main struct TemporaryChatChecks {
    static func main() {
        for spanish in [true, false] {
            let store = CuadraoChatPreview(spanish: spanish)
            let previous = store.current
            let originalDraft = spanish ? "Mi borrador" : "My draft"
            previous.draft = originalDraft
            let attachment = CanvasChatAttachment(name: "sample.pdf", symbol: "doc")
            previous.attachments = [attachment]
            let originalIDs = store.references(spanish).map(\.id)
            store.startTemporary()
            precondition(store.temporary && !store.useContext && !store.contextLocked)
            precondition(!store.hasTemporaryContent && store.current.id != previous.id)
            store.current.draft = " \n "
            precondition(!store.hasTemporaryContent)
            store.current.attachments = [attachment]
            precondition(store.hasTemporaryContent && !store.contextLocked)
            store.useContext = true
            precondition(store.useContext)
            let temporaryID = store.current.id
            store.startTemporary()
            precondition(store.current.id == temporaryID && store.useContext)
            store.send(spanish: spanish)
            precondition(store.contextLocked && store.hasTemporaryContent)
            store.useContext = false
            precondition(store.useContext, "The store must refuse context changes after sending")
            precondition(store.references(spanish).map(\.id) == originalIDs)
            store.leaveTemporary(for: .returnToRegular)
            precondition(store.current === previous && store.current.draft == originalDraft)
            precondition(store.current.attachments.first?.id == attachment.id)
            precondition(!store.temporary && !store.useContext && !store.contextLocked)
            store.endTemporary()
            precondition(store.current === previous)
            store.startTemporary()
            store.current.draft = "Unsent"
            precondition(store.hasTemporaryContent)
            store.leaveTemporary(for: .newRegular)
            precondition(!store.temporary && store.current.id != previous.id)
            precondition(store.current.draft.isEmpty && store.current.attachments.isEmpty)
            let restored = store.threads[0]
            restored.deleted = true; restored.archived = true
            store.startTemporary()
            store.current.draft = "Unsent"
            precondition(restored.deleted)
            store.leaveTemporary(for: .open(restored))
            precondition(store.current === restored && !restored.deleted && !restored.archived)
            let regularID = store.current.id
            let priorTurns = store.current.turns.count
            let draftBeforeCall = "Keep this draft"
            store.current.draft = draftBeforeCall
            store.current.attachments = [attachment]
            store.voice.start()
            precondition(store.voice.active && store.voice.presentation == .compact)
            store.voice.muted = true
            store.voice.phase = .speaking
            precondition(!store.voice.resting, "Muting input must not suppress the speaking state")
            store.voice.interrupt()
            precondition(store.voice.resting && store.voice.active)
            store.voice.presentation = .keyboard
            precondition(store.voice.active && store.current.id == regularID)
            precondition(store.current.draft == draftBeforeCall && store.current.attachments.first?.id == attachment.id)
            store.voice.presentation = .compact
            store.voice.start()
            precondition(store.voice.presentation == .expanded && store.voice.muted)
            store.voice.end()
            precondition(!store.voice.active && store.current.id == regularID)
            precondition(store.current.turns.count == priorTurns && store.current.draft == draftBeforeCall)
            store.voice.start()
            store.startTemporary()
            precondition(!store.voice.active && store.temporary)
            store.voice.start()
            store.voice.end()
            precondition(store.temporary, "Ending voice must not silently end the temporary chat")
            store.voice.start()
            store.leaveTemporary(for: .returnToRegular)
            precondition(!store.voice.active && store.current.id == regularID)
            store.voice.start()
            store.open(store.threads[1])
            precondition(!store.voice.active)
            store.voice.start()
            store.newChat()
            precondition(!store.voice.active && store.current.id != regularID)
            print("PASS: live voice start, mute/speaking, interruption, keyboard handoff, minimization, end and conversation boundaries (\(spanish ? "es" : "en"))")
            print("PASS: temporary entry, whitespace, attachments, context lock, history isolation, draft restoration, new chat and history opening (\(spanish ? "es" : "en"))")
        }
    }
}
