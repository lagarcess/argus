import SwiftUI

/// Decorative preview motion. Replace the illustrated waveform with measured levels at integration.
struct CuadraoVoiceSea: View {
    let voice: CuadraoVoicePreview
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion || voice.resting || scenePhase != .active)) { timeline in
            let time = reduceMotion || voice.resting ? 0 : timeline.date.timeIntervalSinceReferenceDate
            Canvas { context, size in
                let strength = voice.resting ? 0.10 : (voice.phase == .speaking ? 0.64 : 0.44)
                let colors = [Color(red: 0.12, green: 0.53, blue: 0.39),
                              Color(red: 0.38, green: 0.72, blue: 0.56),
                              Color(red: 0.12, green: 0.40, blue: 0.35)]
                for index in 0..<3 {
                    let offset = Double(index) * 2.1
                    let center = CGPoint(x: size.width * (0.18 + Double(index) * 0.32 + sin(time * 0.32 + offset) * 0.12),
                                         y: size.height * (0.96 + cos(time * 0.25 + offset) * 0.035))
                    let radius = size.width * (0.90 + sin(time * 0.22 + offset) * 0.06)
                    context.fill(Path(CGRect(origin: .zero, size: size)), with: .radialGradient(
                        Gradient(colors: [colors[index].opacity(strength * (colorScheme == .dark ? 0.80 : 1)), .clear]),
                        center: center, startRadius: 0, endRadius: radius))
                }
            }
        }.allowsHitTesting(false).accessibilityHidden(true)
    }
}

struct CuadraoVoiceWave: View {
    let voice: CuadraoVoicePreview
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion || voice.resting || scenePhase != .active)) { timeline in
            let time = reduceMotion || voice.resting ? 0 : timeline.date.timeIntervalSinceReferenceDate
            Canvas { context, size in
                let count = 39
                let spacing = size.width / Double(count)
                for index in 0..<count {
                    let position = Double(index) / Double(count - 1)
                    let envelope = sin(position * .pi)
                    let speed = voice.phase == .speaking ? 3.7 : 1.8
                    let pulse = (sin(time * speed + Double(index) * 0.65) + 1) / 2
                    let height = voice.resting ? 4 : 5 + envelope * (8 + pulse * 20)
                    let rect = CGRect(x: Double(index) * spacing, y: (size.height - height) / 2, width: 3, height: height)
                    context.fill(Path(roundedRect: rect, cornerRadius: 2), with: .color(WelcomePalette.pine.opacity(0.25 + envelope * 0.65)))
                }
            }
        }.frame(width: 230, height: 38).accessibilityHidden(true)
    }
}
