import Foundation
import ArgusSession

/// What the person is told after saving, in the founder-approved words (Spanish first).
enum SavedReceiptOutcome: Equatable {
    case saved
    case alreadySaved
    case failed(SavedReceiptFailure)
}

enum SavedReceiptFailure: Equatable {
    case tooLarge, wrongType, limitReached, couldNotSave

    init(_ error: Error) {
        guard case .rejected(_, let code)? = error as? SessionFailure else { self = .couldNotSave; return }
        switch code {
        case "document_too_large": self = .tooLarge
        case "document_media_type_unsupported": self = .wrongType
        case "document_rate_limited": self = .limitReached
        default: self = .couldNotSave
        }
    }
}

/// The four server calls the receipts surface needs. The real one talks to the API; a sample one backs tests.
protocol SavedReceiptsTransport: Sendable {
    func list(limit: Int, offset: Int, identity: SessionSnapshot) async throws -> SavedDocumentPage
    func save(_ bytes: Data, mediaType: String, filename: String, identity: SessionSnapshot) async throws -> SavedDocumentCapture
    func source(_ id: String, identity: SessionSnapshot) async throws -> Data
    func delete(_ id: String, identity: SessionSnapshot) async throws
}

struct SessionSavedReceiptsTransport: SavedReceiptsTransport {
    let controller: SessionController
    func list(limit: Int, offset: Int, identity: SessionSnapshot) async throws -> SavedDocumentPage {
        try await controller.savedDocuments(limit: limit, offset: offset, expectedIdentity: identity)
    }
    func save(_ bytes: Data, mediaType: String, filename: String, identity: SessionSnapshot) async throws -> SavedDocumentCapture {
        try await controller.saveDocument(bytes, mediaType: mediaType, filename: filename, expectedIdentity: identity)
    }
    func source(_ id: String, identity: SessionSnapshot) async throws -> Data {
        try await controller.savedDocumentSource(id, expectedIdentity: identity)
    }
    func delete(_ id: String, identity: SessionSnapshot) async throws {
        try await controller.deleteSavedDocument(id, expectedIdentity: identity)
    }
}

/// The person's saved receipts: list, save, view and delete. Saving stores the file privately and never
/// asks a model to read it, so it creates no expense and changes no balance.
@MainActor
final class SavedReceiptsModel: ObservableObject {
    @Published private(set) var items: [SavedDocument] = []
    @Published private(set) var loading = false
    @Published private(set) var loadFailed = false
    @Published private(set) var saving = false
    @Published private(set) var removing: String?
    @Published var outcome: SavedReceiptOutcome?
    var sessionChanged: ((SessionSnapshot) -> Void)?

    private let transport: any SavedReceiptsTransport
    private let currentSession: @Sendable () async -> SessionSnapshot
    private var identity: SessionSnapshot?
    private var ticket = UUID()
    private var nextOffset: Int?
    private var failedFiles: [(data: Data, name: String, pdf: Bool)] = []

    init(transport: any SavedReceiptsTransport, currentSession: @escaping @Sendable () async -> SessionSnapshot) {
        self.transport = transport
        self.currentSession = currentSession
    }

    convenience init(controller: SessionController) {
        self.init(transport: SessionSavedReceiptsTransport(controller: controller), currentSession: { await controller.snapshot() })
    }

    func bind(_ snapshot: SessionSnapshot?) {
        let next = snapshot?.phase == .authenticated ? snapshot : nil
        guard identity != next else { return }
        identity = next
        ticket = UUID()
        items = []; nextOffset = nil; loading = false; loadFailed = false; saving = false; removing = nil; outcome = nil
        failedFiles = []
    }

    var hasMore: Bool { nextOffset != nil }

    func load() async {
        guard let identity, !loading else { return }
        let mine = ticket
        loading = true; loadFailed = false
        defer { if mine == ticket { loading = false } }
        do {
            let page = try await transport.list(limit: 50, offset: 0, identity: identity)
            guard mine == ticket else { return }
            items = page.items; nextOffset = page.nextOffset
        } catch {
            guard mine == ticket else { return }
            if await identityChanged() { return }
            loadFailed = true
        }
    }

    func loadMore() async {
        guard let identity, let offset = nextOffset, !loading else { return }
        let mine = ticket
        loading = true
        defer { if mine == ticket { loading = false } }
        do {
            let page = try await transport.list(limit: 50, offset: offset, identity: identity)
            guard mine == ticket else { return }
            items += page.items.filter { new in !items.contains { $0.id == new.id } }
            nextOffset = page.nextOffset
        } catch {
            guard mine == ticket else { return }
            _ = await identityChanged()
        }
    }

    /// Saves each captured file. The outcome is the last file's, which is the only one when one file was chosen.
    func save(_ files: [(data: Data, name: String, pdf: Bool)]) async {
        guard let identity, !saving, !files.isEmpty else { return }
        let mine = ticket
        saving = true; outcome = nil; failedFiles = []
        defer { if mine == ticket { saving = false } }
        var last: SavedReceiptOutcome = .saved
        for file in files {
            do {
                let capture = try await transport.save(file.data, mediaType: Self.mediaType(file), filename: file.name, identity: identity)
                last = capture.replayed ? .alreadySaved : .saved
            } catch {
                guard mine == ticket else { return }
                if await identityChanged() { return }
                let failure = SavedReceiptFailure(error)
                if failure == .couldNotSave { failedFiles = files }
                outcome = .failed(failure)
                return
            }
        }
        guard mine == ticket else { return }
        outcome = last
        await load()
    }

    /// Tries again with the files that could not be saved, only after a failure that a retry can fix.
    func retry() async {
        let files = failedFiles
        outcome = nil
        await save(files)
    }

    func remove(_ document: SavedDocument) async {
        guard let identity, removing == nil else { return }
        let mine = ticket
        removing = document.id
        defer { if mine == ticket { removing = nil } }
        do {
            try await transport.delete(document.id, identity: identity)
            guard mine == ticket else { return }
            items.removeAll { $0.id == document.id }
        } catch {
            guard mine == ticket else { return }
            if await identityChanged() { return }
            outcome = .failed(.couldNotSave)
        }
    }

    /// The stored file's bytes for viewing, or nil when it cannot be read.
    func source(of document: SavedDocument) async -> Data? {
        guard let identity, document.sourceAvailable else { return nil }
        do { return try await transport.source(document.id, identity: identity) }
        catch { _ = await identityChanged(); return nil }
    }

    static func mediaType(_ file: (data: Data, name: String, pdf: Bool)) -> String {
        if file.pdf { return "application/pdf" }
        return file.data.starts(with: [0x89, 0x50, 0x4E, 0x47]) ? "image/png" : "image/jpeg"
    }

    /// After a failure: if the session moved on (signed out, another person), start clean and tell the owner.
    private func identityChanged() async -> Bool {
        guard let identity else { return true }
        let snapshot = await currentSession()
        guard snapshot != identity else { return false }
        bind(snapshot)
        sessionChanged?(snapshot)
        return true
    }
}
