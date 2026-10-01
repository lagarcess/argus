import SwiftUI

struct CuadraoLiveVoiceCanvas: View {
    let chat: CuadraoChatPreview
    let spanish: Bool
    let keyboard: () -> Void
    let showProposal: () -> Void
    @State private var choosingVoice = false
    private var es: Bool { spanish }
    private var voice: CuadraoVoicePreview { chat.voice }

    var body: some View {
        ZStack {
            WelcomePalette.background.ignoresSafeArea()
            CuadraoVoiceSea(voice: voice).ignoresSafeArea()
            VStack(spacing: 0) {
                header
                ScrollView {
                    VStack(spacing: 24) {
                        Spacer(minLength: 65)
                        CuadraoBrand().scaleEffect(0.9)
                        Text(voice.status(es)).font(.system(.largeTitle, design: .serif))
                            .multilineTextAlignment(.center).contentTransition(.opacity)
                            .accessibilityIdentifier("voice-status")
                        Text(voice.phase == .speaking
                            ? (es ? "Claro. ¿Qué quieres revisar primero?" : "Of course. What would you like to look at first?")
                            : voice.muted
                                ? (es ? "Activa el micrófono cuando quieras seguir." : "Unmute whenever you want to continue.")
                                : (es ? "Podemos seguir hablando mientras usas Cuadrao." : "We can keep talking while you use Cuadrao."))
                            .font(.body).foregroundStyle(.secondary).multilineTextAlignment(.center)
                            .frame(maxWidth: 310)
                        if voice.phase == .speaking {
                            Button(es ? "Interrumpir" : "Interrupt") { voice.interrupt() }
                                .font(.body.weight(.medium)).frame(minHeight: 44)
                                .accessibilityIdentifier("voice-interrupt")
                        }
                        if chat.temporary {
                            Label { Text(es ? "Chat temporal" : "Temporary chat") } icon: {
                                Image("CuadraoTemporaryChat").resizable().scaledToFit().frame(width: 16, height: 16)
                            }.font(.footnote).foregroundStyle(.secondary)
                        }
                    }.frame(maxWidth: .infinity).padding(.horizontal, 28).padding(.bottom, 24)
                }
                VStack(spacing: 28) {
                    CuadraoVoiceWave(voice: voice)
                    HStack(alignment: .top, spacing: 32) {
                        control(voice.muted ? "mic.slash" : "mic", voice.muted ? (es ? "Activar" : "Unmute") : (es ? "Silenciar" : "Mute"), id: "voice-mute", selected: voice.muted) { voice.muted.toggle() }
                        control("keyboard", es ? "Escribir" : "Type", id: "voice-keyboard", action: keyboard)
                        control("xmark", es ? "Terminar" : "End", id: "voice-end", destructive: true) { voice.end() }
                    }
                    Text(es ? "Vista previa · El micrófono está apagado" : "Preview · The microphone is off")
                        .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }.padding(.horizontal, 24).padding(.bottom, 28)
            }
        }.foregroundStyle(WelcomePalette.ink).tint(WelcomePalette.pine)
            .sheet(isPresented: $choosingVoice) { CuadraoVoicePicker(spanish: es) }
    }

    private var header: some View {
        HStack {
            Button { voice.presentation = .compact } label: {
                Image(systemName: "chevron.down").font(.system(size: 18, weight: .medium))
                    .frame(width: 48, height: 48)
            }.accessibilityLabel(es ? "Minimizar conversación de voz" : "Minimize voice conversation")
                .accessibilityIdentifier("voice-minimize")
            Spacer()
            Button { choosingVoice = true } label: {
                Label(es ? "Elegir voz" : "Choose voice", systemImage: "slider.horizontal.3")
                    .font(.subheadline.weight(.medium)).frame(minHeight: 44)
            }.accessibilityIdentifier("voice-choose")
            Spacer()
            Menu {
                Button(es ? "Ver propuesta de ejemplo" : "Show example proposal", systemImage: "rectangle.on.rectangle", action: showProposal)
                Button(es ? "Probar escucha" : "Preview listening", systemImage: "waveform") { voice.phase = .listening }
                Button(es ? "Probar respuesta" : "Preview speaking", systemImage: "speaker.wave.2") { voice.phase = .speaking }
            } label: {
                Image(systemName: "ellipsis").frame(width: 48, height: 48)
            }.accessibilityLabel(es ? "Estados de la vista previa" : "Preview states")
        }.padding(.horizontal, 16).padding(.top, 8)
    }

    private func control(_ symbol: String, _ title: String, id: String, selected: Bool = false,
                         destructive: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 9) {
                Image(systemName: symbol).font(.system(size: 22, weight: .medium))
                    .frame(width: 60, height: 60)
                    .foregroundStyle(destructive ? Color.white : WelcomePalette.ink)
                    .background(destructive ? Color(red: 0.78, green: 0.19, blue: 0.22) : (selected ? WelcomePalette.sage : WelcomePalette.background.opacity(0.78)), in: Circle())
                Text(title).font(.caption)
            }
        }.buttonStyle(.plain).accessibilityIdentifier(id)
            .accessibilityLabel(title).accessibilityValue(selected ? (es ? "Activado" : "On") : "")
    }
}
