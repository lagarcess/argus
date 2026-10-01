import SwiftUI
import AVFoundation

// A curated preview subset of xAI's documented voices. Preference has one durable owner.
enum CuadraoVoiceOption: String, CaseIterable, Identifiable {
    case ara, eve, sal
    static let preferenceKey = "cuadrao.design.voice"
    var id: String { rawValue }
    var name: String { rawValue.capitalized }
    func detail(_ es: Bool) -> String {
        switch self {
        case .ara: es ? "Cálida y cercana" : "Warm and friendly"
        case .eve: es ? "Vivaz y expresiva" : "Lively and expressive"
        case .sal: es ? "Suave y equilibrada" : "Smooth and balanced"
        }
    }
}

struct CuadraoVoicePreference: View {
    let spanish: Bool
    @AppStorage(CuadraoVoiceOption.preferenceKey) private var selected = CuadraoVoiceOption.ara
    @State private var choosing = false
    var body: some View {
        Button { choosing = true } label: {
            HStack {
                Text(spanish ? "Voz" : "Voice")
                Spacer()
                Text(selected.name).foregroundStyle(.secondary)
                Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
            }.foregroundStyle(.primary).frame(minHeight: 44)
        }.accessibilityIdentifier("voice-preference").accessibilityValue(selected.name)
            .sheet(isPresented: $choosing) { CuadraoVoicePicker(spanish: spanish) }
    }
}

struct CuadraoVoicePicker: View {
    let spanish: Bool
    @AppStorage(CuadraoVoiceOption.preferenceKey) private var selected = CuadraoVoiceOption.ara
    @State private var candidate = CuadraoVoiceOption.ara
    @State private var sample = CuadraoVoiceSamplePlayer()
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    Image(systemName: "waveform").font(.system(size: 36, weight: .light))
                        .foregroundStyle(WelcomePalette.pine).frame(width: 88, height: 88)
                        .background(WelcomePalette.sage.opacity(0.55), in: Circle())
                        .accessibilityHidden(true).padding(.top, 12)
                    Text(spanish ? "Una voz que vaya contigo." : "A voice that feels right.")
                        .font(.system(.title2, design: .serif)).multilineTextAlignment(.center)
                    choices
                    Text(spanish ? "Muestras originales en inglés. Tu conversación puede seguir en español."
                         : "Original English samples. Your conversation can use your preferred language.")
                        .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    if sample.failed {
                        Text(spanish ? "No se pudo reproducir. Vuelve a tocar para intentarlo." : "Couldn't play this sample. Tap again to retry.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }.padding(.horizontal, 24).padding(.bottom, 24)
            }
            .safeAreaInset(edge: .bottom) {
                Button {
                    selected = candidate; sample.stop(); dismiss()
                } label: {
                    Text((spanish ? "Usar " : "Use ") + candidate.name).font(.body.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 52)
                        .foregroundStyle(WelcomePalette.onAccent)
                        .background(WelcomePalette.pine, in: Capsule())
                }.padding(.horizontal, 24).padding(.vertical, 12)
                    .background(WelcomePalette.background)
            }
            .background(WelcomePalette.background).foregroundStyle(WelcomePalette.ink)
            .navigationTitle(spanish ? "Elegir voz" : "Choose voice").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) {
                Button(spanish ? "Cancelar" : "Cancel") { dismiss() }
            } }
        }
        .tint(WelcomePalette.pine)
        .presentationDetents([.large]).presentationDragIndicator(.visible).presentationCornerRadius(32)
        .onAppear { candidate = selected }
        .onDisappear { sample.stop() }
        .onChange(of: scenePhase) { _, phase in if phase != .active { sample.stop() } }
    }

    private var choices: some View {
        VStack(spacing: 0) {
            ForEach(CuadraoVoiceOption.allCases) { option in
                HStack(spacing: 12) {
                    Button { sample.stop(); candidate = option } label: {
                        HStack(spacing: 14) {
                            Image(systemName: candidate == option ? "checkmark.circle.fill" : "circle")
                                .foregroundStyle(candidate == option ? WelcomePalette.pine : Color.secondary)
                            VStack(alignment: .leading, spacing: 5) {
                                Text(option.name).font(.body.weight(.medium))
                                Text(option.detail(spanish)).font(.subheadline).foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 0)
                        }.contentShape(Rectangle()).frame(minHeight: 72)
                    }.buttonStyle(.plain)
                        .accessibilityLabel(option.name + ", " + option.detail(spanish))
                        .accessibilityIdentifier("voice-option-" + option.rawValue)
                        .accessibilityAddTraits(candidate == option ? .isSelected : [])
                    Button { sample.toggle(option) } label: {
                        Image(systemName: sample.playing == option ? "stop.fill" : "play.fill")
                            .font(.system(size: 15)).frame(width: 44, height: 44)
                            .background(WelcomePalette.background, in: Circle())
                    }.buttonStyle(.plain)
                        .accessibilityLabel((sample.playing == option ? (spanish ? "Detener " : "Stop ") : (spanish ? "Escuchar " : "Preview ")) + option.name)
                }.padding(.horizontal, 16)
                if option != CuadraoVoiceOption.allCases.last { Divider().padding(.leading, 50) }
            }
        }.background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 24))
    }

}

@MainActor @Observable final class CuadraoVoiceSamplePlayer: NSObject, AVAudioPlayerDelegate {
    private(set) var playing: CuadraoVoiceOption?
    private(set) var failed = false
    @ObservationIgnored private var player: AVAudioPlayer?
    func toggle(_ option: CuadraoVoiceOption) {
        let wasPlaying = playing == option
        stop(); failed = false
        guard !wasPlaying else { return }
        do {
            guard let url = Bundle.main.url(forResource: "voice_" + option.rawValue, withExtension: "mp3") else {
                failed = true; return
            }
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
            try AVAudioSession.sharedInstance().setActive(true)
            let audio = try AVAudioPlayer(contentsOf: url)
            audio.delegate = self
            player = audio
            guard audio.play() else { failed = true; stop(); return }
            playing = option
        } catch { failed = true; stop() }
    }
    func stop() {
        player?.stop(); player = nil; playing = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor [weak self] in self?.stop() }
    }
}
