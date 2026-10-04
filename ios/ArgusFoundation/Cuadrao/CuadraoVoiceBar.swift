import SwiftUI

struct CuadraoVoiceBar: View {
    let voice: CuadraoVoicePreview
    let spanish: Bool
    var embedded = false

    var body: some View {
        if embedded {
            content
        } else {
            content
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 24))
                .overlay { RoundedRectangle(cornerRadius: 24).stroke(WelcomePalette.separator, lineWidth: 0.5) }
                .padding(.horizontal, 20).padding(.bottom, 8)
        }
    }

    private var content: some View {
        HStack(spacing: 0) {
            Button { voice.presentation = .expanded } label: {
                HStack(spacing: 10) {
                    CuadraoVoiceWave(voice: voice, compact: true)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(voice.resting ? (spanish ? "Silenciado" : "Muted") : voice.status(spanish)).font(.subheadline.weight(.medium)).lineLimit(1)
                        Text(spanish ? "Vista previa" : "Preview").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                    Image(systemName: "arrow.up.left.and.arrow.down.right")
                        .font(.system(size: 12)).foregroundStyle(.secondary).padding(.trailing, 10)
                }.padding(.leading, embedded ? 4 : 16).frame(minHeight: 54).contentShape(Rectangle())
            }.accessibilityLabel(spanish ? "Ampliar voz" : "Expand voice")
                .accessibilityValue(voice.status(spanish))
                .accessibilityIdentifier("voice-expand")
            Button { voice.muted.toggle() } label: {
                Image(systemName: voice.muted ? "mic.slash" : "mic").frame(width: 44, height: 48).contentShape(Rectangle())
            }.accessibilityIdentifier("voice-mute-compact").accessibilityLabel(voice.muted ? (spanish ? "Activar micrófono" : "Unmute microphone") : (spanish ? "Silenciar micrófono" : "Mute microphone"))
            Button { voice.end() } label: {
                Image(systemName: "xmark").frame(width: 44, height: 48).contentShape(Rectangle())
            }.accessibilityLabel(spanish ? "Terminar conversación de voz" : "End voice conversation")
                .accessibilityIdentifier("voice-end-compact")
        }.buttonStyle(.plain).foregroundStyle(WelcomePalette.ink)
    }
}
