import Foundation

@main struct TemporaryChatChecks {
    static func main() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/New_York")!
        let midnight = calendar.date(from: DateComponents(year: 2026, month: 3, day: 9, hour: 0, minute: 5))!
        let yesterday = calendar.date(from: DateComponents(year: 2026, month: 3, day: 8, hour: 0, minute: 1))!
        for spanish in [true, false] {
            precondition(CanvasChatRecency.label(midnight, spanish: spanish, now: midnight, calendar: calendar) == (spanish ? "Hoy" : "Today"))
            precondition(CanvasChatRecency.label(yesterday, spanish: spanish, now: midnight, calendar: calendar) == (spanish ? "Ayer" : "Yesterday"), "Calendar days must handle daylight saving time")
            let old = calendar.date(from: DateComponents(year: 2025, month: 12, day: 31))!
            precondition(CanvasChatRecency.label(old, spanish: spanish, now: midnight, calendar: calendar).contains("2025"))
            let dateStore = CuadraoChatPreview(spanish: spanish)
            precondition(dateStore.current.lastMessageDate == nil)
            dateStore.current.draft = "A real local message"
            dateStore.send(spanish: spanish, now: yesterday)
            let datedThread = dateStore.current
            datedThread.title = "Renamed"; datedThread.pinned = true; datedThread.unread = true
            dateStore.archive(datedThread); dateStore.restore(datedThread)
            precondition(datedThread.lastMessageDate == yesterday, "Metadata actions cannot change message recency")
            dateStore.open(datedThread); datedThread.draft = "Follow up"
            dateStore.send(spanish: spanish, now: midnight)
            precondition(datedThread.lastMessageDate == midnight)

            let voiceOwnerStore = CuadraoChatPreview(spanish: spanish)
            let outerContext = UUID(), innerContext = UUID()
            voiceOwnerStore.presentContext(outerContext)
            voiceOwnerStore.voice.start()
            voiceOwnerStore.presentContext(innerContext)
            precondition(voiceOwnerStore.voiceContextOwner == innerContext && voiceOwnerStore.voice.active)
            voiceOwnerStore.dismissContext(innerContext)
            precondition(voiceOwnerStore.voiceContextOwner == outerContext && voiceOwnerStore.voice.presentation == .compact)
            voiceOwnerStore.voice.presentation = .expanded
            voiceOwnerStore.dismissContext(outerContext)
            precondition(voiceOwnerStore.voiceContextOwner == nil && voiceOwnerStore.voice.active && voiceOwnerStore.voice.presentation == .compact)
            voiceOwnerStore.voice.end()
            voiceOwnerStore.presentContext(outerContext)
            voiceOwnerStore.voiceMessage.begin(liveVoiceActive: false, held: false, now: 1)
            precondition(voiceOwnerStore.voiceMessage.locked)
            voiceOwnerStore.voiceMessage.stop(now: 3)
            voiceOwnerStore.dismissContext(outerContext)
            precondition(voiceOwnerStore.voiceMessage.state == .review, "Closing context retains completed voice review")
            voiceOwnerStore.voiceMessage.cancel()
            voiceOwnerStore.presentContext(outerContext)
            voiceOwnerStore.voiceMessage.begin(liveVoiceActive: false, held: false, now: 4)
            voiceOwnerStore.dismissContext(outerContext)
            precondition(voiceOwnerStore.voiceMessage.state == .idle, "A forced context dismissal stops recording")
            print("PASS: context voice ownership, nested return, minimization and recording lifecycle")

            let contextStore = CuadraoChatPreview(spanish: spanish, includeExamples: false)
            precondition(contextStore.references(spanish).isEmpty)
            let draftThread = contextStore.current
            let contextAttachment = CanvasChatAttachment(name: "receipt.pdf", symbol: "doc")
            draftThread.draft = "Keep this question"
            draftThread.attachments = [contextAttachment]
            let accountFocus = CanvasChatFocus.account(id: UUID(), title: "Cuenta corriente")
            let planFocus = CanvasChatFocus.plan(id: UUID(), title: "Samaná")
            contextStore.selectFocus(accountFocus)
            contextStore.selectFocus(planFocus)
            precondition(contextStore.current === draftThread && draftThread.draft == "Keep this question")
            precondition(draftThread.attachments.first?.id == contextAttachment.id && draftThread.turns.isEmpty)
            draftThread.focus = nil
            precondition(draftThread.draft == "Keep this question" && !draftThread.attachments.isEmpty)
            contextStore.selectFocus(accountFocus)
            contextStore.newChat()
            precondition(contextStore.references(spanish).contains { $0.id == draftThread.id })
            contextStore.open(draftThread)
            contextStore.send(spanish: spanish)
            precondition(draftThread.turns.last?.focus == accountFocus)
            contextStore.selectFocus(planFocus)
            precondition(draftThread.turns.last?.focus == accountFocus, "Sent context is a snapshot")
            precondition(draftThread.focus == planFocus && draftThread.draft.isEmpty && draftThread.attachments.isEmpty)
            let chart = CanvasChartFocus(spaceID: "personal", spaceTitle: "Personal", currency: "DOP",
                interval: DateInterval(start: yesterday, end: midnight), periodTitle: "Mar 8–9", metric: .activity, presentation: .distribution,
                selection: .expenseCategory(id: "food", title: "Comida"))
            contextStore.newChat()
            contextStore.selectFocus(.chart(chart))
            let chartThread = contextStore.current
            contextStore.open(draftThread)
            precondition(chartThread.title.contains(spanish ? "Actividad" : "Activity"))
            precondition(chartThread.focus == .chart(chart))
            contextStore.startTemporary()
            contextStore.selectFocus(planFocus)
            precondition(contextStore.temporary && !contextStore.useContext && contextStore.hasTemporaryContent)
            let privateID = contextStore.current.id
            contextStore.current.draft = "Only this selected plan"
            contextStore.send(spanish: spanish)
            precondition(!contextStore.useContext && contextStore.current.turns.last?.focus == planFocus)
            contextStore.endTemporary()
            precondition(!contextStore.references(spanish).contains { $0.id == privateID })
            contextStore.includeExamples = true
            precondition(contextStore.references(spanish).count > 2)
            contextStore.includeExamples = false
            precondition(contextStore.references(spanish).count == 2, "First use hides examples, not actual drafts")
            print("PASS: focus replacement/removal, draft/attachment continuity, turn snapshots, chart scope, temporary privacy and first-use examples (\(spanish ? "es" : "en"))")

            let receiptChat = CuadraoChatPreview(spanish: spanish)
            let originID = receiptChat.current.id
            let originThread = receiptChat.current
            let receiptID = UUID()
            receiptChat.attachReceipt(receiptID, to: originID)
            receiptChat.newChat()
            receiptChat.attachReceipt(receiptID, to: originID)
            precondition(originThread.receiptIDs == [receiptID] && receiptChat.current.receiptIDs.isEmpty,
                         "Capture callback updates its originating thread once, never the new current thread")
            precondition(originThread.turns.isEmpty, "A saved receipt never sends a message")
            receiptChat.removeReceipt(receiptID)
            precondition(originThread.receiptIDs.isEmpty, "Discard clears the originating card")
            let store = CuadraoChatPreview(spanish: spanish)
            let historyThread = store.threads[0]
            store.open(historyThread)
            historyThread.draft = "Preserve on archive"
            store.voice.start()
            store.archive(historyThread)
            precondition(historyThread.archived && store.current !== historyThread && !store.voice.active)
            precondition(historyThread.draft == "Preserve on archive")
            store.restore(historyThread)
            store.open(historyThread)
            store.delete(historyThread)
            precondition(historyThread.deleted && store.current !== historyThread)
            store.restore(historyThread)
            precondition(!historyThread.deleted && !historyThread.archived)
            let previous = store.current
            let originalDraft = spanish ? "Mi borrador" : "My draft"
            previous.draft = originalDraft
            let attachment = CanvasChatAttachment(name: "sample.pdf", symbol: "doc")
            previous.attachments = [attachment]
            store.startTemporary()
            let originalIDs = store.references(spanish).map(\.id)
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
            store.open(store.threads.first { $0.id != regularID }!)
            precondition(!store.voice.active)
            store.voice.start()
            store.newChat()
            precondition(!store.voice.active && store.current.id != regularID)
            print("PASS: live voice start, mute/speaking, interruption, keyboard handoff, minimization, end and conversation boundaries (\(spanish ? "es" : "en"))")
            print("PASS: temporary entry, whitespace, attachments, context lock, history isolation, draft restoration, new chat and history opening (\(spanish ? "es" : "en"))")
        }
    }
}
