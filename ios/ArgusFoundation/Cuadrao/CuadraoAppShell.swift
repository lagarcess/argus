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
    var addItems: [CuadraoAddItem] = []
    @ViewBuilder let content: (Binding<CuadraoTab>) -> Content
    @State private var pendingTab: CuadraoTab?
    @State private var addOpen = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TabView(selection: tabSelection) { content(tabSelection) }
            .cuadraoScrollBar(edge: .bottom) {
                VStack(spacing: 0) {
                    if chat.voiceContextOwner == nil && selection != .assistant && chat.voice.active && chat.voice.presentation != .expanded {
                        CuadraoVoiceBar(voice: chat.voice, spanish: spanish)
                    }
                    if addOpen && showsNavigation && !addItems.isEmpty {
                        CuadraoAddTray(items: addItems, spanish: spanish) { item in
                            closeAdd()
                            item.perform()
                        }
                        .padding(.bottom, 8)
                        .transition(reduceMotion ? .opacity : .move(edge: .bottom).combined(with: .opacity))
                    }
                    if showsNavigation {
                        ZStack {
                            if chat.voiceMessage.state != .recording {
                                CuadraoNavigationBar(selection: tabSelection, compact: compact, spanish: spanish,
                                    avatar: avatar, profileName: profileName,
                                    addOpen: addOpen, add: toggleAdd)
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
            .onChange(of: showsNavigation) { _, shown in if !shown { closeAdd() } }
            .onChange(of: selection) { _, _ in closeAdd() }
            .cuadraoSoftScrollEdges()
            .cuadraoVoicePresentation(chat: chat, spanish: spanish, ownsPresentation: chat.voiceContextOwner == nil,
                keyboard: {
                    if CuadraoFirstRelease.hasAssistant { selection = .assistant }
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

    private func toggleAdd() {
        guard !addItems.isEmpty else { return }
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.2)) { addOpen.toggle() }
    }

    private func closeAdd() {
        guard addOpen else { return }
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.2)) { addOpen = false }
    }

    private var tabSelection: Binding<CuadraoTab> {
        Binding(get: { selection }, set: { next in
            if next == .assistant && !CuadraoFirstRelease.hasAssistant { return }
            closeAdd()
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
