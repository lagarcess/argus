import SwiftUI

/// Review stays attached to its conversation, including a trip to another surface.
struct CuadraoVoiceMessagePanel: View {
    let message: CuadraoVoiceMessagePreview
    let spanish: Bool
    private var es: Bool { spanish }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: "waveform").foregroundStyle(WelcomePalette.pine)
                Text(message.state == .review
                     ? (es ? "Revisar mensaje · Vista previa" : "Review message · Preview")
                     : (es ? "Mensaje de voz · Vista previa" : "Voice message · Preview"))
                    .font(.subheadline.weight(.medium)).accessibilityIdentifier("voice-message-status")
                Spacer(minLength: 4)
                Text(Duration.seconds(message.duration).formatted(.time(pattern: .minuteSecond)))
                    .monospacedDigit().font(.caption).foregroundStyle(.secondary)
            }
            HStack {
                Button(es ? "Descartar" : "Discard") { message.cancel() }
                Spacer()
                if message.state == .review {
                    Button(es ? "Enviar" : "Send") { message.submit() }
                        .accessibilityIdentifier("voice-message-send")
                }
            }.font(.subheadline.weight(.medium)).frame(minHeight: 44)
            Text(message.state == .submitted
                 ? (es ? "Ejemplo de envío. No se grabó ni envió audio." : "Example submission. No audio was recorded or sent.")
                 : (es ? "Vista previa · No se grabó audio" : "Preview · No audio was recorded"))
                .font(.caption).foregroundStyle(.secondary)
        }.padding(8)
    }
}

struct CuadraoVoiceRecordingOverlay: View {
    let message: CuadraoVoiceMessagePreview
    let spanish: Bool
    @State private var illustration = CuadraoVoicePreview()
    @Environment(\.dynamicTypeSize) private var typeSize
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private var es: Bool { spanish }

    var body: some View {
        ZStack(alignment: .bottom) {
            ZStack {
                if typeSize.isAccessibilitySize { WelcomePalette.background }
                LinearGradient(stops: [.init(color: .clear, location: 0),
                                       .init(color: WelcomePalette.background, location: 0.3),
                                       .init(color: WelcomePalette.background, location: 1)],
                               startPoint: .top, endPoint: .bottom)
                CuadraoVoiceSea(voice: illustration, cancelling: message.cancelArmed)
            }.mask {
                LinearGradient(stops: [.init(color: typeSize.isAccessibilitySize ? .black : .clear, location: 0), .init(color: .black, location: 0.3),
                                       .init(color: .black, location: 1)], startPoint: .top, endPoint: .bottom)
            }.accessibilityHidden(true)
            GeometryReader { geometry in
                ScrollView {
                    recordingContent
                        .frame(width: geometry.size.width)
                        .frame(minHeight: geometry.size.height, alignment: .bottom)
                }.defaultScrollAnchor(typeSize.isAccessibilitySize ? .top : .bottom).scrollBounceBehavior(.basedOnSize)
                    .scrollDisabled(message.held)
            }
        }.accessibilityIdentifier("voice-recording-overlay")
    }

    private var recordingContent: some View {
        VStack(spacing: 22) {
                lockHint
                Text(instruction).font(.subheadline.weight(.medium)).multilineTextAlignment(.center)
                    .foregroundStyle(message.cancelArmed ? Color.red : WelcomePalette.ink)
                    .accessibilityIdentifier("voice-recording-instruction")
                if message.locked {
                    TimelineView(.periodic(from: .now, by: 1)) { _ in
                        Text(Duration.seconds(message.elapsed()).formatted(.time(pattern: .minuteSecond)))
                            .font(.subheadline.monospacedDigit()).foregroundStyle(.secondary)
                    }
                }
                CuadraoVoiceWave(voice: illustration, cancelling: message.cancelArmed)
                if message.locked {
                    let layout = typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(spacing: 16)) : AnyLayout(HStackLayout(spacing: 24))
                    layout {
                        Button(es ? "Cancelar" : "Cancel", role: .destructive) { message.cancel() }
                            .frame(minWidth: 80, minHeight: 48).fixedSize(horizontal: false, vertical: true).accessibilityIdentifier("voice-message-cancel")
                        Button { message.stop() } label: {
                            Label(es ? "Detener" : "Stop", systemImage: "stop.fill")
                                .font(.body.weight(.medium)).fixedSize(horizontal: false, vertical: true)
                                .padding(.horizontal, 22).padding(.vertical, 10).frame(minHeight: 48)
                                .foregroundStyle(WelcomePalette.onAccent)
                                .background(WelcomePalette.pine, in: Capsule())
                        }.accessibilityIdentifier("voice-message-stop")
                    }.buttonStyle(.plain)
                }
                Text(es ? "Vista previa · El micrófono está apagado" : "Preview · The microphone is off")
                    .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }.padding(.horizontal, 28).padding(.top, 24).padding(.bottom, 48)
    }

    private var lockHint: some View {
        HStack(spacing: 12) {
            Image(systemName: message.locked ? "lock.fill" : "lock.open")
                .font(.system(size: 20, weight: .medium))
                .offset(y: reduceMotion ? 0 : -6 * message.lockProgress)
                .frame(width: 36, height: 44)
                .contentTransition(reduceMotion ? .identity : .symbolEffect(.replace))
            Text(message.locked
                 ? (es ? "Sin mantener" : "Hands-free")
                 : (es ? "↑ Desliza arriba para fijar" : "↑ Slide up to lock"))
                .font(.footnote.weight(.medium)).fixedSize(horizontal: false, vertical: true)
        }.padding(.horizontal, 16).padding(.vertical, 4)
            .background(.regularMaterial, in: Capsule())
            .foregroundStyle(WelcomePalette.pine)
            .opacity(message.cancelArmed ? 0.35 : 1)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.12), value: message.lockProgress)
            .accessibilityLabel(message.locked ? (es ? "Grabación fijada" : "Recording locked")
                                : (es ? "Desliza arriba para grabar sin mantener" : "Slide up to record hands-free"))
    }

    private var instruction: String {
        if message.cancelArmed { return es ? "Suelta para cancelar" : "Release to cancel" }
        if message.locked {
            return message.held ? (es ? "Puedes soltar" : "You can let go")
                : (es ? "Graba tu mensaje. Cuadrao responderá por escrito." : "Record your message. Cuadrao will reply in text.")
        }
        return es ? "Suelta para enviar\nDesliza a la izquierda para cancelar"
            : "Release to send\nSlide left to cancel"
    }
}
