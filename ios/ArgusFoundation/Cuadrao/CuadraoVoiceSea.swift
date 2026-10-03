import SwiftUI

/// Decorative preview motion. Replace the illustrated waveform with measured levels at integration.
struct CuadraoVoiceSea: View {
    let voice: CuadraoVoicePreview
    var cancelling = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion || voice.resting || scenePhase != .active)) { timeline in
            let time = reduceMotion ? 0 : timeline.date.timeIntervalSinceReferenceDate
            Canvas { context, size in
                let strength = voice.phase == .speaking ? 0.54 : 0.42
                let colors = cancelling ? [Color.red, Color(red: 0.95, green: 0.35, blue: 0.35), Color.red] : [Color(red: 0.12, green: 0.53, blue: 0.39),
                              Color(red: 0.38, green: 0.72, blue: 0.56),
                              Color(red: 0.12, green: 0.40, blue: 0.35)]
                for index in 0..<3 {
                    let offset = Double(index) * 2.1
                    let center = CGPoint(x: size.width * (0.18 + Double(index) * 0.32 + sin(time * 0.32 + offset) * 0.12),
                                         y: size.height * (0.86 + cos(time * 0.22 + offset) * 0.045))
                    let radius = size.width * (1.10 + sin(time * 0.20 + offset) * 0.08)
                    context.fill(Path(CGRect(origin: .zero, size: size)), with: .radialGradient(
                        Gradient(colors: [colors[index].opacity(strength * (colorScheme == .dark ? 0.80 : 1)), .clear]),
                        center: center, startRadius: 0, endRadius: radius))
                }
            }
        }.opacity(voice.resting ? 0.24 : 1)
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.6), value: voice.resting)
            .allowsHitTesting(false).accessibilityHidden(true)
    }
}

struct CuadraoVoiceWave: View {
    let voice: CuadraoVoicePreview
    var compact = false
    var cancelling = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion || voice.resting || scenePhase != .active)) { timeline in
            let time = reduceMotion ? 0 : timeline.date.timeIntervalSinceReferenceDate
            Canvas { context, size in
                let count = compact ? 5 : 39
                let spacing = size.width / Double(count)
                for index in 0..<count {
                    let position = Double(index) / Double(count - 1)
                    let envelope = sin(position * .pi)
                    let speed = voice.phase == .speaking ? 3.7 : 1.8
                    let pulse = (sin(time * speed + Double(index) * 0.65) + 1) / 2
                    let height = voice.resting ? 3 : 4 + envelope * (compact ? 4 + pulse * 12 : 8 + pulse * 20)
                    let rect = CGRect(x: Double(index) * spacing, y: (size.height - height) / 2, width: 3, height: height)
                    context.fill(Path(roundedRect: rect, cornerRadius: 2), with: .color((cancelling ? Color.red : WelcomePalette.pine).opacity(0.25 + envelope * 0.65)))
                }
            }
        }.frame(width: compact ? 25 : 230, height: compact ? 26 : 38).accessibilityHidden(true)
    }
}
