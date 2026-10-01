import Foundation
import Observation

/// Presentation rehearsal only. This object never captures, uploads or invents audio/transcripts.
@Observable final class CuadraoVoiceMessagePreview {
    enum State { case idle, recording, review, submitted }
    enum DragFeedback { case none, cancelChanged, locked }
    static let lockDistance = 88.0
    static let holdDelay = 0.35
    static let minimumDuration = 0.45
    static let cancelDistance = 70.0
    private(set) var state = State.idle
    private(set) var startedAt = 0.0
    private(set) var duration = 0.0
    private(set) var held = false
    private(set) var locked = false
    private(set) var lockProgress = 0.0
    private(set) var cancelArmed = false
    private(set) var tooShort = false

    func begin(liveVoiceActive: Bool, held: Bool, now: Double = ProcessInfo.processInfo.systemUptime) {
        guard !liveVoiceActive, (state == .idle || state == .submitted) else { return }
        state = .recording; startedAt = now; duration = 0
        self.held = held; locked = !held; lockProgress = held ? 0 : 1
        cancelArmed = false; tooShort = false
    }
    @discardableResult
    func drag(leftwardDistance: Double, upwardDistance: Double) -> DragFeedback {
        guard state == .recording, held, !locked else { return .none }
        let wasArmed = cancelArmed
        // One dominant direction owns the gesture; diagonal ties favor cancellation.
        cancelArmed = leftwardDistance >= Self.cancelDistance && leftwardDistance >= abs(upwardDistance)
        lockProgress = upwardDistance > abs(leftwardDistance) * 1.2
            ? min(1, max(0, upwardDistance / Self.lockDistance)) : 0
        if lockProgress == 1 {
            locked = true; cancelArmed = false
            return .locked
        }
        return wasArmed != cancelArmed ? .cancelChanged : .none
    }
    func release(now: Double = ProcessInfo.processInfo.systemUptime) {
        guard state == .recording, held else { return }
        if locked { held = false; return }
        finish(submit: true, now: now)
    }
    func stop(now: Double = ProcessInfo.processInfo.systemUptime) {
        guard state == .recording, !held else { return }
        finish(submit: false, now: now)
    }
    func submit() {
        guard state == .review else { return }
        state = .submitted
    }
    func cancel() {
        state = .idle; cancelArmed = false; duration = 0; held = false; locked = false; lockProgress = 0; tooShort = false
    }
    func elapsed(now: Double = ProcessInfo.processInfo.systemUptime) -> Double {
        state == .recording ? max(0, now - startedAt) : duration
    }
    private func finish(submit: Bool, now: Double) {
        if cancelArmed { cancel(); return }
        duration = max(0, now - startedAt)
        guard duration >= Self.minimumDuration else {
            cancel(); tooShort = true; return
        }
        held = false
        state = submit ? .submitted : .review
    }
}
