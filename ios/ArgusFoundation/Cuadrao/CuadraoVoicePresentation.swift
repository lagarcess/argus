import SwiftUI

extension View {
    func cuadraoVoicePresentation(chat: CuadraoChatPreview, spanish: Bool, ownsPresentation: Bool,
                                 keyboard: @escaping () -> Void, showProposal: (() -> Void)? = nil) -> some View {
        modifier(CuadraoVoicePresentation(chat: chat, spanish: spanish, ownsPresentation: ownsPresentation,
                                          keyboard: keyboard, showProposal: showProposal))
    }
}

private struct CuadraoVoicePresentation: ViewModifier {
    let chat: CuadraoChatPreview
    let spanish: Bool
    let ownsPresentation: Bool
    let keyboard: () -> Void
    let showProposal: (() -> Void)?
    @Environment(\.dynamicTypeSize) private var typeSize

    func body(content: Content) -> some View {
        content
            .overlay(alignment: .bottom) {
                if ownsPresentation && chat.voiceMessage.state == .recording {
                    GeometryReader { geometry in
                        CuadraoVoiceRecordingOverlay(message: chat.voiceMessage, spanish: spanish)
                            .frame(height: typeSize.isAccessibilitySize ? geometry.size.height : min(460, geometry.size.height))
                            .frame(maxHeight: .infinity, alignment: .bottom)
                    }.ignoresSafeArea(edges: .bottom)
                        .allowsHitTesting(chat.voiceMessage.locked && !chat.voiceMessage.held)
                }
            }
            .fullScreenCover(isPresented: Binding(
                get: { ownsPresentation && chat.voice.active && chat.voice.presentation == .expanded },
                set: { if !$0 && ownsPresentation && chat.voice.active && chat.voice.presentation == .expanded { chat.voice.presentation = .compact } })) {
                CuadraoLiveVoiceCanvas(chat: chat, spanish: spanish, keyboard: keyboard, showProposal: showProposal)
            }
    }
}
