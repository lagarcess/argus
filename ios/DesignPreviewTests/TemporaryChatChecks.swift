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
            let message = CuadraoVoiceMessagePreview()
            message.begin(liveVoiceActive: true, held: true, now: 10)
            precondition(message.state == .idle)
            message.begin(liveVoiceActive: false, held: true, now: 10)
            message.release(now: 10.1)
            precondition(message.state == .idle && message.tooShort)
            message.begin(liveVoiceActive: false, held: true, now: 20)
            message.release(now: 21)
            precondition(message.state == .submitted && message.duration == 1)
            message.begin(liveVoiceActive: false, held: true, now: 30)
            message.drag(leftwardDistance: CuadraoVoiceMessagePreview.cancelDistance, upwardDistance: 0)
            message.release(now: 31)
            precondition(message.state == .idle)
            message.begin(liveVoiceActive: false, held: true, now: 40)
            message.drag(leftwardDistance: CuadraoVoiceMessagePreview.cancelDistance, upwardDistance: 0)
            message.drag(leftwardDistance: 0, upwardDistance: 0)
            message.release(now: 41)
            precondition(message.state == .submitted)
            message.begin(liveVoiceActive: false, held: true, now: 50)
            message.cancel(); message.release(now: 51)
            precondition(message.state == .idle)
            message.begin(liveVoiceActive: false, held: true, now: 55)
            message.drag(leftwardDistance: 0, upwardDistance: CuadraoVoiceMessagePreview.lockDistance / 2)
            precondition(!message.locked && message.lockProgress == 0.5)
            message.drag(leftwardDistance: 0, upwardDistance: CuadraoVoiceMessagePreview.lockDistance)
            precondition(message.locked && !message.cancelArmed && message.held)
            message.drag(leftwardDistance: 200, upwardDistance: 0)
            message.release(now: 57)
            precondition(message.state == .recording && message.locked && !message.held,
                         "Lifting a locked recording must never submit it")
            message.stop(now: 58)
            precondition(message.state == .review && message.duration == 3)
            message.cancel()
            message.begin(liveVoiceActive: false, held: true, now: 59)
            message.drag(leftwardDistance: 100, upwardDistance: 100)
            precondition(message.cancelArmed && !message.locked, "A diagonal cannot arm both actions")
            message.cancel()
            message.begin(liveVoiceActive: false, held: false, now: 60)
            message.release(now: 61)
            precondition(message.state == .recording && message.locked)
            message.stop(now: 62)
            precondition(message.state == .review && message.duration == 2)
            message.begin(liveVoiceActive: false, held: true, now: 63)
            precondition(message.state == .review, "A pending review cannot be overwritten by another recording")
            message.submit()
            precondition(message.state == .submitted)
            precondition(store.current.draft == draftBeforeCall && store.current.attachments.first?.id == attachment.id)
            store.voiceMessage.begin(liveVoiceActive: false, held: false, now: 70)
            store.voiceMessage.stop(now: 71)
            store.newChat()
            precondition(store.voiceMessage.state == .idle, "A recording cannot cross conversation boundaries")
            store.open(restored)
            print("PASS: hold, left cancel, up lock, diagonal disambiguation, accessible recording, review and interruption")
            store.voice.start()
            precondition(store.voice.active && store.voice.presentation == .expanded)
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
            store.startTemporary()
            store.voiceMessage.begin(liveVoiceActive: false, held: false, now: 80)
            store.voiceMessage.stop(now: 81)
            precondition(store.hasTemporaryContent, "Pending voice review needs the temporary discard guard")
            store.endTemporary()
            precondition(store.voiceMessage.state == .idle)
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
