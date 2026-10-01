import SwiftUI

enum CanvasChatSheet: Identifiable {
    case history, rename, temporary, sources, calculation, share, states, dictation, voice
    case attachment(String)
    var id: String { String(describing: self) }
}

struct CuadraoChatSheet: View {
    let destination: CanvasChatSheet
    let store: CuadraoChatPreview
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var title = ""
    @State private var historyScope = 0
    @State private var transcript = ""
    @State private var endTemporary = false
    @State private var pendingExit = CuadraoChatPreview.Exit.returnToRegular
    private var es: Bool { spanish }
    private var heading: String {
        switch destination {
        case .history: "Chats"
        case .rename: es ? "Cambiar nombre" : "Rename"
        case .temporary: es ? "Chat temporal" : "Temporary chat"
        case .sources: es ? "Sobre esta respuesta" : "About this answer"
        case .calculation: es ? "El cálculo" : "The calculation"
        case .share: es ? "Compartir chat" : "Share chat"
        case .states: es ? "Vista previa" : "Preview"
        case .dictation: es ? "Revisar dictado" : "Review dictation"
        case .voice: es ? "Conversación por voz" : "Voice conversation"
        case .attachment: es ? "Añadir al mensaje" : "Add to message"
        }
    }
    var body: some View {
        NavigationStack {
            Group {
                if case .history = destination { history }
                else { ScrollView { content.padding(24).frame(maxWidth: .infinity, alignment: .leading) } }
            }
            .background(WelcomePalette.background).foregroundStyle(WelcomePalette.ink)
            .navigationTitle(heading).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) {
                Button(es ? "Listo" : "Done") { dismiss() }
            } }
        }
        .presentationDragIndicator(.visible)
        .onAppear { title = store.current.title; transcript = es ? "Quiero organizar mis gastos del mes." : "I want to organize my monthly spending." }
        .confirmationDialog(es ? "¿Terminar el chat temporal?" : "End temporary chat?", isPresented: $endTemporary, titleVisibility: .visible) {
            Button(es ? "Terminar chat" : "End chat", role: .destructive) { finishExit() }
            Button(es ? "Seguir aquí" : "Stay here", role: .cancel) {}
        } message: { Text(es ? "Se descartarán los mensajes y adjuntos de este chat temporal. Tu chat anterior quedará intacto." : "This temporary chat’s messages and attachments will be discarded. Your previous chat stays intact.") }
    }

    @ViewBuilder private var content: some View {
        @Bindable var store = store
        VStack(alignment: .leading, spacing: 24) {
            switch destination {
            case .history: EmptyView()
            case .rename:
                TextField(es ? "Nombre del chat" : "Chat name", text: $title).textFieldStyle(.roundedBorder)
                action(es ? "Guardar" : "Save") { store.current.title = String(title.trimmingCharacters(in: .whitespacesAndNewlines).prefix(80)); dismiss() }
                    .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            case .temporary:
                CuadraoTemporaryChatSettings(store: store, spanish: es) { requestExit(.returnToRegular) }
            case .calculation:
                Text("DOP " + CanvasChatCalculation.amount(CanvasChatCalculation.total)).font(.system(.largeTitle, design: .rounded))
                detail(es ? "Aporte mensual" : "Monthly contribution", "DOP " + CanvasChatCalculation.amount(CanvasChatCalculation.monthly))
                detail(es ? "Meses" : "Months", String(CanvasChatCalculation.months))
                Divider()
                Text(es ? "Aporte mensual × meses. Sin intereses, comisiones ni retiros." : "Monthly contribution × months. No interest, fees or withdrawals.")
                previewNote
            case .sources:
                Label(es ? "Conocimiento general" : "General knowledge", systemImage: "book")
                Text(es ? "Esta respuesta de ejemplo explica conceptos. No consultó fuentes externas ni tasas actuales." : "This example explains concepts. It did not consult external sources or current rates.")
                Text(es ? "Cuando una respuesta use fuentes, podrás abrir aquí cada título, fecha y enlace." : "When an answer uses sources, you will be able to open each title, date and link here.").foregroundStyle(.secondary)
            case .share:
                Text(store.current.title).font(.title3)
                Text(es ? "Revisa lo que compartirás antes de crear un enlace." : "Review what you will share before creating a link.")
                previewNote
            case .states:
                Text(es ? "Explora los estados del diseño. No se envían mensajes a una IA." : "Explore the design states. No messages are sent to an AI.")
                ForEach(CanvasChatResponseState.allCases, id: \.self) { value in
                    Button { store.responseState = value; dismiss() } label: {
                        HStack {
                            Text(stateTitle(value)); Spacer()
                            if store.responseState == value { Image(systemName: "checkmark") }
                        }.frame(minHeight: 44)
                    }
                }
            case .dictation:
                Text(es ? "Transcripción de ejemplo" : "Example transcript").font(.footnote).foregroundStyle(.secondary)
                TextField(es ? "Revisa el texto" : "Review the text", text: $transcript, axis: .vertical)
                    .lineLimit(3...8).padding(16).background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 16))
                action(es ? "Usar texto" : "Use text") {
                    store.current.draft = [store.current.draft, transcript].filter { !$0.isEmpty }.joined(separator: " "); dismiss()
                }.disabled(transcript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                Text(es ? "El micrófono permanece apagado en esta vista previa." : "The microphone stays off in this preview.").font(.footnote).foregroundStyle(.secondary)
            case .voice:
                Image(systemName: "waveform").font(.system(size: 40)).foregroundStyle(WelcomePalette.pine)
                Text(es ? "Hablar y escuchar, sin escribir." : "Talk and listen, without typing.").font(.title2)
                previewNote
            case .attachment(let symbol):
                Image(systemName: symbol).font(.system(size: 36)).foregroundStyle(WelcomePalette.pine)
                let name = symbol == "doc" ? (es ? "Documento de ejemplo.pdf" : "Example document.pdf") : (es ? "Recibo de ejemplo" : "Example receipt")
                Text(name).font(.title3)
                Text(es ? "Prueba cómo aparece un archivo antes de enviarlo." : "Try how a file appears before sending it.")
                action(es ? "Adjuntar ejemplo" : "Attach example") {
                    store.current.attachments.append(CanvasChatAttachment(name: name, symbol: symbol))
                    dismiss()
                }
                Text(es ? "No se accede a tus archivos, fotos ni cámara." : "Your files, photos and camera are not accessed.").font(.footnote).foregroundStyle(.secondary)
            }
        }
    }

    private var history: some View {
        let rows = store.threads.filter {
            (historyScope == 2 ? $0.deleted : !$0.deleted && $0.archived == (historyScope == 1))
                && (query.isEmpty || $0.title.localizedStandardContains(query))
        }.sorted { $0.pinned && !$1.pinned }
        return VStack(spacing: 12) {
            Picker(es ? "Ver chats" : "Show chats", selection: $historyScope) {
                Text(es ? "Recientes" : "Recent").tag(0)
                Text(es ? "Archivados" : "Archived").tag(1)
                Text(es ? "Eliminados" : "Deleted").tag(2)
            }.pickerStyle(.segmented).padding(.horizontal, 24)
            List {
                if rows.isEmpty {
                    ContentUnavailableView(es ? "Sin chats" : "No chats", systemImage: "bubble.left.and.bubble.right",
                        description: Text(es ? "Prueba otra búsqueda o empieza un chat." : "Try another search or start a chat."))
                }
                ForEach(rows) { thread in
                    Button {
                        requestExit(.open(thread))
                    } label: {
                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(thread.title).font(.body).lineLimit(2)
                                Text(thread.deleted ? (es ? "Toca para restaurar" : "Tap to restore") : (es ? "Conversación de ejemplo" : "Example conversation"))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if thread.pinned { Image(systemName: "pin").font(.caption).foregroundStyle(.secondary) }
                            if thread.unread { Circle().fill(WelcomePalette.pine).frame(width: 7, height: 7) }
                        }.padding(.vertical, 8)
                    }.listRowBackground(WelcomePalette.background).foregroundStyle(WelcomePalette.ink)
                        .swipeActions { if thread.archived { Button(es ? "Restaurar" : "Restore") { thread.archived = false } } }
                }
            }.listStyle(.plain).searchable(text: $query, prompt: es ? "Buscar chats" : "Search chats")
            Button {
                requestExit(.newRegular)
            } label: { Label(es ? "Nuevo chat" : "New chat", systemImage: "square.and.pencil").frame(minHeight: 44) }
            Text(es ? "Vista previa · Conversaciones locales de ejemplo" : "Preview · Local example conversations")
                .font(.caption).foregroundStyle(.secondary).padding(.bottom, 16)
        }
    }
    private func requestExit(_ destination: CuadraoChatPreview.Exit) {
        pendingExit = destination
        if store.hasTemporaryContent { endTemporary = true } else { finishExit() }
    }
    private func finishExit() { store.leaveTemporary(for: pendingExit); dismiss() }
    private var previewNote: some View {
        Text(es ? "Vista previa de diseño. No se crea un enlace, se guarda información ni se conecta a un servicio." : "Design preview. No link is created, information saved or service connected.")
            .font(.footnote).foregroundStyle(.secondary)
    }
    private func detail(_ label: String, _ value: String) -> some View {
        HStack { Text(label).foregroundStyle(.secondary); Spacer(); Text(value).monospacedDigit() }
    }
    private func action(_ title: String, _ perform: @escaping () -> Void) -> some View {
        Button(action: perform) { Text(title).font(.body.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 52)
            .foregroundStyle(WelcomePalette.onAccent).background(WelcomePalette.pine, in: RoundedRectangle(cornerRadius: 16)) }
    }
    private func stateTitle(_ value: CanvasChatResponseState) -> String {
        switch value {
        case .complete: es ? "Respuesta completa" : "Complete answer"
        case .waiting: es ? "Esperando respuesta" : "Waiting for an answer"
        case .failed: es ? "Error de conexión" : "Connection error"
        }
    }
}
