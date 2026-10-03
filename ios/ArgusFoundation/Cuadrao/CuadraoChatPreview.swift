import SwiftUI
import Observation

// Presentation state only. This store never calls an assistant or writes financial records.
@Observable final class CanvasChatThread: Identifiable {
    let id: String
    var title: String
    var turns: [CanvasChatTurn] = []
    var receiptIDs: [UUID] = []
    var focus: CanvasChatFocus?
    var draft = ""
    var attachments: [CanvasChatAttachment] = []
    var pinned = false
    var archived = false
    var deleted = false
    var unread = false
    var example = false
    var lastMessageDate: Date? { turns.last?.createdAt }
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
    var createdAt: Date = .now
    var focus: CanvasChatFocus? = nil
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
    private let spanish: Bool
    var includeExamples: Bool
    var visibleThreads: [CanvasChatThread] { threads.filter { includeExamples || !$0.example } }
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

    init(spanish: Bool, includeExamples: Bool = true) {
        self.spanish = spanish
        self.includeExamples = includeExamples
        for (index, item) in CanvasSearchReference.examples(spanish).filter({ $0.kind == .chats }).enumerated() {
            let thread = CanvasChatThread(id: item.id, title: item.title)
            thread.example = true
            thread.turns = [CanvasChatTurn(question: item.content, attachments: [],
                example: item.id == "chat-cd" ? .certificate : nil,
                createdAt: Calendar.current.date(byAdding: .day, value: -index, to: .now)!)]
            threads.append(thread)
        }
    }
    func attachReceipt(_ receiptID: UUID, to threadID: String) {
        let thread = threads.first { $0.id == threadID } ?? (current.id == threadID ? current : nil)
        guard let thread, !thread.receiptIDs.contains(receiptID) else { return }
        thread.receiptIDs.append(receiptID)
        if !threads.contains(where: { $0.id == thread.id }) { threads.append(thread) }
    }
    func removeReceipt(_ id: UUID) {
        for thread in threads { thread.receiptIDs.removeAll { $0 == id } }
        current.receiptIDs.removeAll { $0 == id }
    }
    func selectFocus(_ focus: CanvasChatFocus) { current.focus = focus }
    private func retainDraft() {
        guard !temporary, !current.deleted, !current.archived,
              !current.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !current.attachments.isEmpty || current.focus != nil,
              !threads.contains(where: { $0.id == current.id }) else { return }
        if current.title.isEmpty {
            current.title = String(current.draft.trimmingCharacters(in: .whitespacesAndNewlines).prefix(80))
            if current.title.isEmpty { current.title = current.attachments.first?.name ?? current.focus?.title(spanish) ?? "" }
        }
        threads.insert(current, at: 0)
    }
    var hasTemporaryContent: Bool {
        temporary && (!current.turns.isEmpty || !current.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !current.attachments.isEmpty || current.focus != nil || voiceMessage.state != .idle)
    }
    func newChat() { retainDraft(); voice.end(); voiceMessage.cancel(); current = CanvasChatThread(); responseState = .complete }
    func open(_ thread: CanvasChatThread) { if current.id != thread.id { retainDraft(); voice.end(); voiceMessage.cancel() }; current = thread; thread.unread = false; responseState = .complete }
    func startTemporary() {
        guard !temporary else { return }
        retainDraft(); suspended = current; temporary = true; contextEnabled = false; newChat()
    }
    func endTemporary() {
        guard temporary else { return }
        voice.end(); voiceMessage.cancel()
        current = suspended ?? CanvasChatThread(); suspended = nil; temporary = false; contextEnabled = false
        responseState = .complete
    }
    func archive(_ thread: CanvasChatThread) {
        thread.archived = true
        if current.id == thread.id { newChat() }
    }
    func delete(_ thread: CanvasChatThread) {
        thread.deleted = true
        if current.id == thread.id { newChat() }
    }
    func restore(_ thread: CanvasChatThread) { thread.deleted = false; thread.archived = false }
    enum Exit { case returnToRegular, newRegular, open(CanvasChatThread) }
    // Call only after the presentation has confirmed any temporary content loss.
    func leaveTemporary(for destination: Exit) {
        endTemporary()
        switch destination {
        case .returnToRegular: break
        case .newRegular: newChat()
        case .open(let thread):
            if thread.deleted { restore(thread) }
            open(thread)
        }
    }
    func send(example: CanvasChatExample? = nil, spanish: Bool, now: Date = .now) {
        let text = example?.question(spanish) ?? current.draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty || !current.attachments.isEmpty else { return }
        if current.title.isEmpty { current.title = String(text.prefix(80)) }
        current.turns.append(CanvasChatTurn(question: text, attachments: current.attachments, example: example ?? (current.attachments.isEmpty ? nil : .document), createdAt: now, focus: current.focus))
        current.draft = ""; current.attachments = []; responseState = .complete
        if !temporary && !threads.contains(where: { $0.id == current.id }) { threads.insert(current, at: 0) }
    }
    func references(_ es: Bool) -> [CanvasSearchReference] {
        visibleThreads.filter { !$0.deleted }.map { thread in
            CanvasSearchReference(id: thread.id, kind: .chats, title: thread.title,
                detail: thread.archived ? (es ? "Chat archivado · Solo yo" : "Archived chat · Only me")
                    : (es ? "Conversación · Solo yo" : "Conversation · Only me"),
                content: thread.turns.last?.question ?? thread.draft, source: es ? "Conversación" : "Conversation")
        }
    }
}

/// Both history and Search render the last message date, never a metadata edit time.
enum CanvasChatRecency {
    static func label(_ date: Date, spanish: Bool, now: Date = .now, calendar: Calendar = .current) -> String {
        if calendar.isDate(date, inSameDayAs: now) { return spanish ? "Hoy" : "Today" }
        if let yesterday = calendar.date(byAdding: .day, value: -1, to: now),
           calendar.isDate(date, inSameDayAs: yesterday) { return spanish ? "Ayer" : "Yesterday" }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: spanish ? "es-419" : "en_US")
        formatter.calendar = calendar
        formatter.timeZone = calendar.timeZone
        formatter.setLocalizedDateFormatFromTemplate(calendar.component(.year, from: date) == calendar.component(.year, from: now) ? "dMMM" : "dMMMy")
        return formatter.string(from: date)
    }
}
