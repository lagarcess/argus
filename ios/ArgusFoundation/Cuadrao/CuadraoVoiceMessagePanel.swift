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
            // Both alternatives keep their measured space throughout the gesture.
            ZStack {
                lockHint.opacity(message.locked ? 0 : 1)
                    .accessibilityHidden(message.locked)
                TimelineView(.periodic(from: .now, by: 1)) { _ in
                    Label(Duration.seconds(message.elapsed()).formatted(.time(pattern: .minuteSecond)), systemImage: "lock.fill")
                        .font(.subheadline.monospacedDigit()).foregroundStyle(WelcomePalette.pine)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(es ? "Grabación sin mantener" : "Hands-free recording")
                        .accessibilityValue(Duration.seconds(message.elapsed()).formatted(.time(pattern: .minuteSecond)))
                        .accessibilityIdentifier("voice-recording-timer")
                }.opacity(message.locked ? 1 : 0).accessibilityHidden(!message.locked)
            }.frame(maxWidth: .infinity)
            CuadraoVoiceWave(voice: illustration, cancelling: message.cancelArmed)
            ZStack {
                Text(instruction).font(.subheadline.weight(.medium)).multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .foregroundStyle(message.cancelArmed ? Color.red : WelcomePalette.ink)
                    .opacity(message.held ? 1 : 0).accessibilityHidden(!message.held)
                    .accessibilityIdentifier("voice-recording-instruction")
                // Measure the longest hint even when the current hint is shorter.
                Text(holdInstruction)
                    .font(.subheadline.weight(.medium)).multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true).hidden().accessibilityHidden(true)
                recordingActions.opacity(message.held ? 0 : 1)
                    .allowsHitTesting(!message.held).accessibilityHidden(message.held)
            }.frame(maxWidth: .infinity)
            Text(es ? "Vista previa · Micrófono apagado" : "Preview · Microphone off")
                .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }.padding(.horizontal, 28).padding(.top, 24).padding(.bottom, 48)
    }

    private var recordingActions: some View {
        let layout = typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(spacing: 16)) : AnyLayout(HStackLayout(spacing: 24))
        return layout {
            Button(role: .destructive) { message.cancel() } label: {
                Text(es ? "Cancelar" : "Cancel").frame(minWidth: 80, minHeight: 48).contentShape(Rectangle())
            }.buttonStyle(.plain).fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("voice-message-cancel")
            Button { message.stop() } label: {
                Label(es ? "Detener" : "Stop", systemImage: "stop.fill")
                    .font(CuadraoTypography.action).fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 22).padding(.vertical, 10).frame(minHeight: 48)
                    .foregroundStyle(WelcomePalette.onAccent)
                    .background(WelcomePalette.pine, in: Capsule())
            }.buttonStyle(.plain).accessibilityIdentifier("voice-message-stop")
        }
    }

    private var lockHint: some View {
        Label(es ? "↑ Desliza para fijar" : "↑ Slide to lock", systemImage: "lock.open")
            .font(.footnote.weight(.medium)).fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, 16).frame(minHeight: 48)
            .background(.regularMaterial, in: Capsule())
            .foregroundStyle(WelcomePalette.pine)
            .opacity(message.cancelArmed ? 0.35 : 1)
            .accessibilityIdentifier("voice-lock-hint")
            .accessibilityLabel(es ? "Desliza arriba para grabar sin mantener" : "Slide up to record hands-free")
    }

    private var instruction: String {
        if message.cancelArmed { return es ? "Suelta para cancelar" : "Release to cancel" }
        if message.locked { return es ? "Puedes soltar" : "You can let go" }
        return holdInstruction
    }

    private var holdInstruction: String {
        es ? "Suelta para enviar\n← Desliza para cancelar" : "Release to send\n← Slide to cancel"
    }
}
