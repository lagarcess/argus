import Foundation
import Observation

/// Presentation rehearsal only. This object never captures, uploads or invents audio/transcripts.
@Observable final class CuadraoVoiceMessagePreview {
    enum State { case idle, recording, review, submitted }
    static let holdDelay = 0.35
    static let minimumDuration = 0.45
    static let cancelDistance = 70.0
    private(set) var state = State.idle
    private(set) var startedAt = 0.0
    private(set) var duration = 0.0
    private(set) var held = false
    private(set) var cancelArmed = false
    private(set) var tooShort = false

    func begin(liveVoiceActive: Bool, held: Bool, now: Double = ProcessInfo.processInfo.systemUptime) {
        guard !liveVoiceActive, (state == .idle || state == .submitted) else { return }
        state = .recording; startedAt = now; duration = 0
        self.held = held; cancelArmed = false; tooShort = false
    }
    func drag(upwardDistance: Double) {
        guard state == .recording, held else { return }
        cancelArmed = upwardDistance >= Self.cancelDistance
    }
    func release(now: Double = ProcessInfo.processInfo.systemUptime) {
        guard state == .recording, held else { return }
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
        state = .idle; cancelArmed = false; duration = 0; held = false; tooShort = false
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
