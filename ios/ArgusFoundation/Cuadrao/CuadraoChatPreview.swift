import SwiftUI
import Observation

// Presentation state only. This store never calls an assistant or writes financial records.
@Observable final class CanvasChatThread: Identifiable {
    let id: String
    var title: String
    var turns: [CanvasChatTurn] = []
    var draft = ""
    var attachments: [CanvasChatAttachment] = []
    var pinned = false
    var archived = false
    var deleted = false
    var unread = false
    init(id: String = UUID().uuidString, title: String = "") { self.id = id; self.title = title }
}

struct CanvasChatAttachment: Identifiable {
    let id = UUID()
    let name: String
    let symbol: String
}

struct CanvasChatTurn: Identifiable {
    let id = UUID()
    let question: String
    let attachments: [CanvasChatAttachment]
    let example: CanvasChatExample?
}

enum CanvasChatExample: String, CaseIterable, Identifiable {
    case savings, certificate, document
    var id: Self { self }
    func title(_ es: Bool) -> String {
        switch self {
        case .savings: es ? "Ponerle números a una meta" : "Put numbers to a goal"
        case .certificate: es ? "Entender un certificado" : "Understand a certificate"
        case .document: es ? "Revisar un documento" : "Review a document"
        }
    }
    func question(_ es: Bool) -> String {
        switch self {
        case .savings: es ? "Si separo 3,000 pesos al mes, ¿cuánto junto en seis meses?" : "If I set aside 3,000 pesos a month, how much will I have in six months?"
        case .certificate: es ? "¿Qué debo mirar antes de abrir un certificado de depósito?" : "What should I look at before opening a certificate of deposit?"
        case .document: es ? "Ayúdame a revisar este documento." : "Help me review this document."
        }
    }
}

enum CanvasChatResponseState: String, CaseIterable { case complete, waiting, failed }

@Observable final class CuadraoChatPreview {
    let voice = CuadraoVoicePreview()
    let voiceMessage = CuadraoVoiceMessagePreview()
    var threads: [CanvasChatThread] = []
    var current = CanvasChatThread()
    var temporary = false
    private var contextEnabled = false
    var contextLocked: Bool { temporary && !current.turns.isEmpty }
    var useContext: Bool {
        get { contextEnabled }
        set { if temporary && !contextLocked { contextEnabled = newValue } }
    }
    var responseState = CanvasChatResponseState.complete
    private var suspended: CanvasChatThread?

    init(spanish: Bool) {
        for item in CanvasSearchReference.examples(spanish).filter({ $0.kind == .chats }) {
            let thread = CanvasChatThread(id: item.id, title: item.title)
            thread.turns = [CanvasChatTurn(question: item.content, attachments: [],
                example: item.id == "chat-cd" ? .certificate : nil)]
            threads.append(thread)
        }
    }
    var hasTemporaryContent: Bool {
        temporary && (!current.turns.isEmpty || !current.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !current.attachments.isEmpty || voiceMessage.state != .idle)
    }
    func newChat() { voice.end(); voiceMessage.cancel(); current = CanvasChatThread(); responseState = .complete }
    func open(_ thread: CanvasChatThread) { if current.id != thread.id { voice.end(); voiceMessage.cancel() }; current = thread; thread.unread = false; responseState = .complete }
    func startTemporary() {
        guard !temporary else { return }
        suspended = current; temporary = true; contextEnabled = false; newChat()
    }
    func endTemporary() {
        guard temporary else { return }
        voice.end(); voiceMessage.cancel()
        current = suspended ?? CanvasChatThread(); suspended = nil; temporary = false; contextEnabled = false
        responseState = .complete
    }
    enum Exit { case returnToRegular, newRegular, open(CanvasChatThread) }
    // Call only after the presentation has confirmed any temporary content loss.
    func leaveTemporary(for destination: Exit) {
        endTemporary()
        switch destination {
        case .returnToRegular: break
        case .newRegular: newChat()
        case .open(let thread):
            if thread.deleted { thread.deleted = false; thread.archived = false }
            open(thread)
        }
    }
    func send(example: CanvasChatExample? = nil, spanish: Bool) {
        let text = example?.question(spanish) ?? current.draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty || !current.attachments.isEmpty else { return }
        if current.title.isEmpty { current.title = String(text.prefix(80)) }
        current.turns.append(CanvasChatTurn(question: text, attachments: current.attachments, example: example ?? (current.attachments.isEmpty ? nil : .document)))
        current.draft = ""; current.attachments = []; responseState = .complete
        if !temporary && !threads.contains(where: { $0.id == current.id }) { threads.insert(current, at: 0) }
    }
    func references(_ es: Bool) -> [CanvasSearchReference] {
        threads.filter { !$0.deleted }.map { thread in
            CanvasSearchReference(id: thread.id, kind: .chats, title: thread.title,
                detail: thread.archived ? (es ? "Chat archivado · Solo yo" : "Archived chat · Only me")
                    : (es ? "Conversación · Solo yo" : "Conversation · Only me"),
                content: thread.turns.last?.question ?? "", source: es ? "Conversación de ejemplo" : "Example conversation")
        }
    }
}
