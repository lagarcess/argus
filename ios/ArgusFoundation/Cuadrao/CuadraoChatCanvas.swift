import SwiftUI

struct CuadraoChatCanvas: View {
    let store: CuadraoChatPreview
    let spanish: Bool
    @Binding var editing: Bool
    @State private var sheet: CanvasChatSheet?
    @State private var tray = false
    @State private var ending = false
    @FocusState private var focused: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var es: Bool { spanish }
    private var active: Bool { !store.current.turns.isEmpty }
    private var ready: Bool { !store.current.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !store.current.attachments.isEmpty }

    var body: some View {
        @Bindable var thread = store.current
        VStack(spacing: 0) {
            header
            if active { conversation } else { welcome }
            composer(thread: $thread.draft)
        }
        .safeAreaPadding(.bottom, focused ? 0 : 80)
        .background(WelcomePalette.background)
        .foregroundStyle(WelcomePalette.ink)
        .toolbar(.hidden, for: .tabBar)
        .onChange(of: focused) { _, value in editing = value; if value { tray = false } }
        .onDisappear { focused = false; editing = false }
        .sheet(item: $sheet) { destination in
            CuadraoChatSheet(destination: destination, store: store, spanish: es)
                .tint(WelcomePalette.pine)
        }
        .confirmationDialog(es ? "¿Terminar el chat temporal?" : "End temporary chat?", isPresented: $ending, titleVisibility: .visible) {
            Button(es ? "Terminar y crear chat" : "End and create chat", role: .destructive) { store.leaveTemporary(for: .newRegular) }
            Button(es ? "Seguir aquí" : "Stay here", role: .cancel) {}
        } message: {
            Text(es ? "Se descartará esta conversación. Tu chat anterior quedará intacto." : "This conversation will be discarded. Your previous chat stays intact.")
        }
    }

    private var header: some View {
        HStack(spacing: 0) {
            control("clock.arrow.circlepath", es ? "Chats recientes" : "Recent chats", id: "chat-history") { sheet = .history }
            if active || store.temporary {
                control("square.and.pencil", store.temporary ? (es ? "Nuevo chat normal" : "New regular chat") : (es ? "Nuevo chat" : "New chat"), id: "chat-new") {
                    if store.hasTemporaryContent { ending = true }
                    else { store.leaveTemporary(for: .newRegular) }
                }
            } else { Color.clear.frame(width: 44, height: 44) }
            Spacer(minLength: 8)
            if active && !store.temporary {
                control("square.and.arrow.up", es ? "Compartir chat" : "Share chat", id: "chat-share") { sheet = .share }
                Menu {
                    Button(es ? "Cambiar nombre" : "Rename", systemImage: "pencil") { sheet = .rename }
                    Button(es ? (store.current.pinned ? "Desfijar" : "Fijar") : (store.current.pinned ? "Unpin" : "Pin"), systemImage: "pin") { store.current.pinned.toggle() }
                    Button(es ? "Marcar como no leído" : "Mark unread", systemImage: "envelope.badge") { store.current.unread = true }
                    Button(es ? "Archivar" : "Archive", systemImage: "archivebox") { store.current.archived = true; store.newChat() }
                    Button(es ? "Eliminar" : "Delete", systemImage: "trash", role: .destructive) { store.current.deleted = true; store.newChat() }
                    Divider()
                    Button(es ? "Estados de vista previa" : "Preview states", systemImage: "slider.horizontal.3") { sheet = .states }
                } label: { Image(systemName: "ellipsis").frame(width: 44, height: 44) }
                    .accessibilityLabel(es ? "Opciones del chat" : "Chat options")
            } else {
                Button {
                    if store.temporary { sheet = .temporary } else {
                        focused = false; tray = false
                        withAnimation(reduceMotion ? nil : .easeOut(duration: 0.15)) { store.startTemporary() }
                    }
                } label: {
                    Image("CuadraoTemporaryChat").resizable().scaledToFit().frame(width: 24, height: 24)
                        .frame(width: 44, height: 44)
                        .background(store.temporary ? WelcomePalette.surface : .clear, in: Circle())
                }.accessibilityLabel(store.temporary ? (es ? "Opciones del chat temporal" : "Temporary chat settings") : (es ? "Iniciar chat temporal" : "Start temporary chat"))
                    .accessibilityValue(store.temporary ? (es ? "Activo" : "Active") : "")
                    .accessibilityIdentifier("chat-temporary")
            }
        }.foregroundStyle(WelcomePalette.ink).padding(.horizontal, 18).padding(.top, 6)
    }

    private var welcome: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 18) {
                    Spacer(minLength: 24)
                    if store.temporary {
                        Image("CuadraoTemporaryChat").resizable().scaledToFit().frame(width: 36, height: 36).foregroundStyle(.secondary)
                        Text(es ? "Chat temporal" : "Temporary chat").font(.system(.title, design: .serif))
                        Text(es ? "Fuera de tu historial.\nSin nuevas memorias." : "Outside your history.\nNo new memories.")
                            .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        Button { sheet = .temporary } label: {
                            HStack(spacing: 6) {
                                Text(store.useContext ? (es ? "Con mi contexto" : "Using my context") : (es ? "Sin mi contexto" : "Without my context"))
                                Image(systemName: "chevron.down").font(.caption2)
                            }.font(.subheadline).frame(minHeight: 44)
                        }
                    } else {
                        CuadraoBrand().scaleEffect(0.85).accessibilityLabel("Cuadrao")
                        Text(es ? "¿Qué vemos hoy?" : "What shall we look at?")
                            .font(.system(.largeTitle, design: .serif)).multilineTextAlignment(.center)
                    }
                    Spacer(minLength: 32)
                }.frame(maxWidth: .infinity, minHeight: geometry.size.height).padding(.horizontal, 24)
            }.scrollDismissesKeyboard(.interactively)
        }
    }

    private var conversation: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 32) {
                    if store.temporary {
                        Button { sheet = .temporary } label: {
                            Label { Text((es ? "Temporal · " : "Temporary · ") + (store.useContext ? (es ? "Con mi contexto" : "Using my context") : (es ? "Sin mi contexto" : "Without my context"))) } icon: {
                                Image("CuadraoTemporaryChat").resizable().scaledToFit().frame(width: 16, height: 16)
                            }
                                .font(.caption).foregroundStyle(.secondary)
                        }.frame(maxWidth: .infinity, minHeight: 44)
                    }
                    ForEach(store.current.turns) { turn in
                        VStack(alignment: .leading, spacing: 24) {
                            VStack(alignment: .trailing, spacing: 8) {
                                ForEach(turn.attachments) { item in CanvasChatAttachmentChip(item: item, spanish: es) }
                                if !turn.question.isEmpty {
                                    Text(turn.question).font(.body).textSelection(.enabled)
                                        .padding(.horizontal, 17).padding(.vertical, 13)
                                        .background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 22))
                                }
                            }.frame(maxWidth: .infinity, alignment: .trailing).padding(.leading, 28)
                            if turn.id == store.current.turns.last?.id && store.responseState != .complete {
                                responseState
                            } else {
                                CuadraoChatAnswer(turn: turn, spanish: es, showSources: { sheet = .sources }, showDetails: { sheet = .calculation })
                            }
                        }.id(turn.id)
                    }
                    Color.clear.frame(height: 1).id("chat-bottom")
                }.padding(.horizontal, 24).padding(.vertical, 24)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: store.current.turns.count) { _, _ in proxy.scrollTo("chat-bottom", anchor: .bottom) }
            .onChange(of: focused) { _, value in if value { proxy.scrollTo("chat-bottom", anchor: .bottom) } }
            .overlay(alignment: .bottomTrailing) {
                if store.current.turns.count > 1 {
                    Button { withAnimation(reduceMotion ? nil : .easeOut(duration: 0.2)) { proxy.scrollTo("chat-bottom", anchor: .bottom) } } label: {
                        Image(systemName: "arrow.down").frame(width: 44, height: 44).background(.regularMaterial, in: Circle())
                    }.accessibilityLabel(es ? "Ir al último mensaje" : "Go to latest message").padding(.trailing, 24)
                }
            }
        }
    }

    private var responseState: some View {
        VStack(alignment: .leading, spacing: 12) {
            if store.responseState == .waiting {
                HStack { ProgressView(); Text(es ? "Preparando respuesta…" : "Preparing a response…") }
            } else {
                Label(es ? "No se pudo cargar la respuesta" : "The response could not load", systemImage: "wifi.slash")
            }
            Text(es ? "Estado de ejemplo. No hay una solicitud en curso." : "Example state. No request is running.")
                .font(.caption).foregroundStyle(.secondary)
            Button(es ? "Ver respuesta de ejemplo" : "Show example response") { store.responseState = .complete }
        }.font(.subheadline)
    }

    private func composer(thread: Binding<String>) -> some View {
        VStack(spacing: 10) {
            if !active && !store.temporary && !focused && !tray {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(CanvasChatExample.allCases) { sample in
                            Button { if sample == .document { sheet = .attachment("doc") } else { store.send(example: sample, spanish: es) } } label: {
                                Text(sample.title(es)).font(.subheadline).padding(.horizontal, 16).frame(minHeight: 44)
                                    .overlay { Capsule().stroke(WelcomePalette.separator, lineWidth: 1) }
                            }.buttonStyle(.plain)
                        }
                    }.padding(.horizontal, 20)
                }
            }
            VStack(alignment: .leading, spacing: 12) {
                if !store.current.attachments.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack {
                            ForEach(store.current.attachments) { item in
                                CanvasChatAttachmentChip(item: item, spanish: es) { store.current.attachments.removeAll { $0.id == item.id } }
                            }
                        }
                    }
                }
                TextField(es ? "Escribe un mensaje" : "Write a message", text: thread, axis: .vertical)
                    .font(.body).lineLimit(1...6).focused($focused)
                    .padding(.horizontal, 6).padding(.top, 4)
                    .accessibilityIdentifier("chat-composer")
                HStack {
                    control(tray ? "xmark" : "plus", tray ? (es ? "Cerrar adjuntos" : "Close attachments") : (es ? "Adjuntar" : "Attach"), id: "chat-attach") {
                        focused = false
                        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.2)) { tray.toggle() }
                    }
                    Spacer()
                    control("mic", es ? "Dictar mensaje" : "Dictate message", id: "chat-dictate") { focused = false; sheet = .dictation }
                    Button {
                        focused = false; tray = false
                        if ready { store.send(spanish: es) } else { sheet = .voice }
                    } label: {
                        Image(systemName: ready ? "arrow.up" : "waveform")
                            .font(.system(size: 19, weight: .semibold))
                            .foregroundStyle(WelcomePalette.onAccent).frame(width: 44, height: 44)
                            .background(WelcomePalette.pine, in: Circle())
                    }.accessibilityLabel(ready ? (es ? "Enviar" : "Send") : (es ? "Conversación por voz" : "Voice conversation"))
                        .accessibilityIdentifier("chat-send")
                }
                if tray {
                    Divider()
                    HStack(spacing: 8) {
                        attachmentButton("camera", es ? "Recibo" : "Receipt")
                        attachmentButton("photo", es ? "Foto" : "Photo")
                        attachmentButton("doc", es ? "Archivo" : "File")
                    }.padding(.bottom, 4)
                }
            }.padding(12).background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 26))
                .padding(.horizontal, 16)
        }.padding(.top, 8).padding(.bottom, 8)
    }

    private func attachmentButton(_ symbol: String, _ title: String) -> some View {
        Button { tray = false; sheet = .attachment(symbol) } label: {
            VStack(spacing: 9) { Image(systemName: symbol).font(.title3); Text(title).font(.caption) }
                .frame(maxWidth: .infinity, minHeight: 70)
        }.buttonStyle(.plain)
    }
    private func control(_ symbol: String, _ label: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) { Image(systemName: symbol).font(.system(size: 19)).frame(width: 44, height: 44) }
            .buttonStyle(.plain).accessibilityLabel(label).accessibilityIdentifier(id)
    }
}
