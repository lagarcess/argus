import SwiftUI

enum CuadraoAppShellMetrics {
    static let navigationHeight: CGFloat = 72
}

struct CuadraoAppShell<Content: View>: View {
    @Binding var selection: CuadraoTab
    let chat: CuadraoChatPreview
    let spanish: Bool
    let showsNavigation: Bool
    let compact: Bool
    let avatar: CuadraoAvatarSelection
    let profileName: String
    var showProposal: (() -> Void)? = nil
    @ViewBuilder let content: (Binding<CuadraoTab>) -> Content
    @State private var pendingTab: CuadraoTab?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TabView(selection: tabSelection) { content(tabSelection) }
            .cuadraoScrollBar(edge: .bottom) {
                VStack(spacing: 0) {
                    if chat.voiceContextOwner == nil && selection != .assistant && chat.voice.active && chat.voice.presentation != .expanded {
                        CuadraoVoiceBar(voice: chat.voice, spanish: spanish)
                    }
                    if showsNavigation {
                        ZStack {
                            if chat.voiceMessage.state != .recording {
                                CuadraoNavigationBar(selection: tabSelection, compact: compact, spanish: spanish,
                                    avatar: avatar, profileName: profileName)
                                    .padding(.horizontal, 20)
                                    .frame(height: 64, alignment: .bottom)
                                    .padding(.bottom, 8)
                                    .transition(.opacity)
                            }
                        }.frame(height: CuadraoAppShellMetrics.navigationHeight)
                            .animation(reduceMotion ? nil : .easeOut(duration: 0.18), value: chat.voiceMessage.state == .recording)
                    }
                }
            }
            .cuadraoSoftScrollEdges()
            .cuadraoVoicePresentation(chat: chat, spanish: spanish, ownsPresentation: chat.voiceContextOwner == nil,
                keyboard: {
                    selection = .assistant
                    chat.voice.presentation = .keyboard
                }, showProposal: showProposal.map { show in {
                    show()
                    selection = .plan
                    chat.voice.presentation = .compact
                } })
            .confirmationDialog(spanish ? "¿Terminar el chat temporal?" : "End temporary chat?",
                isPresented: Binding(get: { pendingTab != nil }, set: { if !$0 { pendingTab = nil } }), titleVisibility: .visible) {
                Button(spanish ? "Terminar y salir" : "End and leave", role: .destructive) {
                    let destination = pendingTab
                    chat.leaveTemporary(for: .returnToRegular)
                    pendingTab = nil
                    if let destination { selection = destination }
                }
                Button(spanish ? "Seguir aquí" : "Stay here", role: .cancel) { pendingTab = nil }
            } message: {
                Text(spanish ? "Se descartará el contenido temporal. Tu chat anterior quedará intacto." : "Temporary content will be discarded. Your previous chat stays intact.")
            }
            .tint(WelcomePalette.pine)
            .foregroundStyle(WelcomePalette.ink)
            .environment(\.cuadraoChat, chat)
    }

    private var tabSelection: Binding<CuadraoTab> {
        Binding(get: { selection }, set: { next in
            if selection == .assistant && next != .assistant && chat.hasTemporaryContent {
                pendingTab = next
            } else {
                if selection == .assistant && next != .assistant && chat.temporary {
                    chat.leaveTemporary(for: .returnToRegular)
                }
                selection = next
            }
        })
    }
}
