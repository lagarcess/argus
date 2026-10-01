import SwiftUI

struct CuadraoVoiceMessagePanel: View {
    let message: CuadraoVoiceMessagePreview
    let spanish: Bool
    private var es: Bool { spanish }
    private var color: Color { message.cancelArmed ? .red : WelcomePalette.pine }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: message.cancelArmed ? "xmark.circle" : "waveform").foregroundStyle(color)
                Text(title).font(.subheadline.weight(.medium))
                    .accessibilityIdentifier("voice-message-status")
                Spacer()
                if message.state == .recording {
                    TimelineView(.periodic(from: .now, by: 1)) { _ in
                        Text(Duration.seconds(message.elapsed()).formatted(.time(pattern: .minuteSecond)))
                            .monospacedDigit().font(.subheadline).foregroundStyle(.secondary)
                    }
                }
            }
            if message.state == .recording {
                Text(message.held
                    ? (message.cancelArmed ? (es ? "Suelta para cancelar" : "Release to cancel")
                       : (es ? "Suelta para enviar · Desliza arriba para cancelar" : "Release to send · Slide up to cancel"))
                    : (es ? "Detén el mensaje cuando termines." : "Stop the message when you're finished."))
                    .font(.footnote).foregroundStyle(color)
                if !message.held {
                    HStack {
                        Button(es ? "Cancelar" : "Cancel") { message.cancel() }
                        Spacer()
                        Button(es ? "Detener" : "Stop") { message.stop() }
                            .accessibilityIdentifier("voice-message-stop")
                    }.font(.subheadline.weight(.medium)).frame(minHeight: 44)
                }
            } else {
                HStack {
                    Button(es ? "Descartar" : "Discard") { message.cancel() }
                    Spacer()
                    if message.state == .review {
                        Button(es ? "Enviar" : "Send") { message.submit() }
                            .accessibilityIdentifier("voice-message-send")
                    }
                }.font(.subheadline.weight(.medium)).frame(minHeight: 44)
            }
            Text(message.state == .submitted
                 ? (es ? "Ejemplo de envío. No se grabó ni envió audio." : "Example submission. No audio was recorded or sent.")
                 : (es ? "Vista previa · El micrófono está apagado" : "Preview · The microphone is off"))
                .font(.caption).foregroundStyle(.secondary)
        }.padding(8)
    }
    private var title: String {
        switch message.state {
        case .idle: ""
        case .recording: message.cancelArmed ? (es ? "Cancelar mensaje" : "Cancel message") : (es ? "Grabando mensaje" : "Recording message")
        case .review: es ? "Revisar mensaje · Vista previa" : "Review message · Preview"
        case .submitted: es ? "Mensaje de voz · Vista previa" : "Voice message · Preview"
        }
    }
}

struct CuadraoVoiceRecordingOverlay: View {
    let message: CuadraoVoiceMessagePreview
    let spanish: Bool
    @State private var illustration = CuadraoVoicePreview()
    var body: some View {
        ZStack(alignment: .bottom) {
            LinearGradient(stops: [.init(color: .clear, location: 0),
                                   .init(color: WelcomePalette.background, location: 0.35),
                                   .init(color: WelcomePalette.background, location: 1)],
                           startPoint: .top, endPoint: .bottom)
            CuadraoVoiceSea(voice: illustration, cancelling: message.cancelArmed)
            VStack(spacing: 26) {
                Text(message.cancelArmed
                     ? (spanish ? "Suelta para cancelar" : "Release to cancel")
                     : (spanish ? "Suelta para enviar, desliza arriba para cancelar" : "Release to send, slide up to cancel"))
                    .font(.subheadline).multilineTextAlignment(.center)
                    .foregroundStyle(message.cancelArmed ? Color.red : WelcomePalette.ink)
                CuadraoVoiceWave(voice: illustration, cancelling: message.cancelArmed)
                Text(spanish ? "Vista previa · El micrófono está apagado" : "Preview · The microphone is off")
                    .font(.caption).foregroundStyle(.secondary)
            }.padding(.horizontal, 28).padding(.bottom, 150)
        }.mask {
            LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .black, location: 0.35),
                                   .init(color: .black, location: 1)], startPoint: .top, endPoint: .bottom)
        }.accessibilityElement(children: .combine)
            .accessibilityIdentifier("voice-recording-overlay")
    }
}
