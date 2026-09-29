import SwiftUI
import ArgusSession

struct FinancialSearchOrigin: Codable, Equatable {
    var query = ""
    var kind: FinancialSearchKind?
    var currency: String?
    var pages = 1
    var anchor: String?
    var anchorOffset: Double = 0
}

struct FinancialSearchRestoration: Equatable {
    let id = UUID()
    let anchor: String
    let offset: Double
    var permitsBoundaryFallback = false

    enum Adjustment: Equatable { case complete, move(Double), waitForLayout }

    func adjustment(rowOffset: Double, contentOffset: Double, minimum: Double, maximum: Double) -> Adjustment {
        let delta = rowOffset - offset
        if abs(delta) < 0.5 { return .complete }
        let target = min(maximum, max(minimum, contentOffset + delta))
        if abs(target - contentOffset) < 0.5 {
            return permitsBoundaryFallback ? .complete : .waitForLayout
        }
        return .move(target)
    }
}

@MainActor
final class FinancialSearchModel: ObservableObject {
    enum Destination { case account(UUID), activity(UUID) }
    @Published private(set) var origin = FinancialSearchOrigin()
    @Published private(set) var items: [FinancialSearchHit] = []
    @Published private(set) var cursor: String?
    @Published private(set) var loading = false
    @Published private(set) var errorKey: String?
    @Published private(set) var destination: Destination?
    @Published private(set) var opening = false
    @Published private(set) var destinationError: String?
    @Published private(set) var restoration: FinancialSearchRestoration?
    @Published private(set) var ownerID: String?
    var sessionChanged: ((SessionSnapshot) -> Void)?
    private let controller: SessionController
    private let defaults: UserDefaults
    private let prefix: String
    private var identity: SessionSnapshot?
    private var request = UUID()
    private var detailRequest = UUID()
    private var loaded = false
    private var dirty = true

    init(controller: SessionController, defaults: UserDefaults = .standard, prefix: String = "financial.search.origin.") {
        self.controller = controller; self.defaults = defaults; self.prefix = prefix
    }

    func bind(_ snapshot: SessionSnapshot?) {
        let next = snapshot?.phase == .authenticated ? snapshot : nil
        guard identity != next else { return }
        let nextOwner = next?.profile?.id
        request = UUID(); detailRequest = UUID()
        if ownerID != nextOwner {
            if let ownerID { defaults.removeObject(forKey: prefix + ownerID) }
            origin = FinancialSearchOrigin()
            if let nextOwner, let bytes = defaults.data(forKey: prefix + nextOwner),
               let saved = try? JSONDecoder().decode(FinancialSearchOrigin.self, from: bytes),
               saved.query.count <= 512, (1...10000).contains(saved.pages) { origin = saved }
        }
        identity = next; ownerID = nextOwner
        items = []; cursor = nil; destination = nil; opening = false; destinationError = nil
        loading = false; errorKey = nil; loaded = false; dirty = true; restoration = nil
    }

    func update(query: String? = nil, kind: FinancialSearchKind?? = nil, currency: String?? = nil) {
        var next = origin
        if let query { next.query = String(query.prefix(512)) }
        if let kind { next.kind = kind }
        if let currency { next.currency = currency }
        guard next != origin else { return }
        origin = next
        detailRequest = UUID(); opening = false; destinationError = nil; destination = nil; restoration = nil
        origin.pages = 1; origin.anchor = nil; origin.anchorOffset = 0
        request = UUID(); loading = false; items = []; cursor = nil; loaded = false; dirty = true; errorKey = nil
        persist()
    }

    func remember(anchor: String, offset: Double) {
        guard !loading, restoration == nil, destination == nil, !opening else { return }
        origin.anchor = anchor; origin.anchorOffset = offset; persist()
    }

    func restored(_ id: UUID) {
        guard restoration?.id == id else { return }
        restoration = nil
    }

    func userScrolled() { restoration = nil }

    func invalidate() { dirty = true }
    func activate() async { if !loaded || dirty { await refresh() } }
    func refresh() async { await load(append: false) }
    func more() async { guard cursor != nil, !loading else { return }; await load(append: true) }

    private func load(append: Bool) async {
        guard let identity else { return }
        let ticket = UUID(); request = ticket
        let descriptor = origin
        let targetPages = append ? 1 : descriptor.pages
        let initialCursor = append ? cursor : nil
        loading = true; errorKey = nil
        defer { if request == ticket { loading = false } }
        do {
            var nextCursor = initialCursor
            var collected: [FinancialSearchHit] = []
            var count = 0
            var restarted = false
            var target = targetPages
            while true {
                do {
                    let page = try await controller.financialSearch(query: descriptor.query, kind: descriptor.kind,
                        currency: descriptor.currency, cursor: nextCursor, expectedIdentity: identity)
                    guard request == ticket, self.identity == identity else { return }
                    collected += page.items; nextCursor = page.nextCursor; count += 1
                    if nextCursor == nil || count >= target { break }
                } catch SessionFailure.rejected(_, let code) where code == "financial_search_stale_cursor" && !restarted {
                    restarted = true; collected = []; nextCursor = nil; count = 0
                    target = append ? descriptor.pages + 1 : descriptor.pages
                    continue
                }
            }
            guard request == ticket, self.identity == identity else { return }
            let oldItems = items
            items = append && !restarted ? items + collected : collected
            cursor = nextCursor
            origin.pages = append && !restarted ? descriptor.pages + count : count
            origin.pages = max(1, origin.pages)
            let anchorRemoved = descriptor.anchor.map { anchor in !items.contains(where: { $0.id == anchor }) } ?? false
            if let anchor = descriptor.anchor, anchorRemoved {
                let index = oldItems.firstIndex { $0.id == anchor } ?? 0
                origin.anchor = items.isEmpty ? nil : items[min(index, items.count - 1)].id
            }
            loaded = true; dirty = false; persist()
            if !append || restarted {
                restoration = origin.anchor.map {
                    FinancialSearchRestoration(anchor: $0, offset: origin.anchorOffset, permitsBoundaryFallback: anchorRemoved)
                }
            }
        } catch {
            guard request == ticket else { return }
            await failed(error, identity: identity, ticket: ticket, detail: false)
        }
    }

    func open(_ hit: FinancialSearchHit, accounts: AccountsModel, loop: FinancialLoopModel) async {
        guard let identity, !opening else { return }
        let ticket = UUID(); detailRequest = ticket
        opening = true; destinationError = nil
        defer { if detailRequest == ticket { opening = false } }
        do {
            switch hit {
            case .account(let account):
                let live = try await controller.financialAccount(id: account.id, expectedIdentity: identity)
                guard detailRequest == ticket, self.identity == identity else { return }
                accounts.upsert(live); destination = .account(live.id)
            case .activity(let activity, _):
                _ = try await controller.financialActivityDetail(activity.activityId, expectedIdentity: identity)
                guard detailRequest == ticket, self.identity == identity else { return }
                await accounts.load()
                guard detailRequest == ticket, self.identity == identity else { return }
                destination = .activity(activity.activityId)
            case .expectation(let expectation):
                let live = try await controller.financialExpectation(expectation.id, expectedIdentity: identity)
                guard detailRequest == ticket, self.identity == identity else { return }
                await loop.plan.refresh()
                guard detailRequest == ticket, self.identity == identity else { return }
                guard loop.plan.errorKey == nil else { throw SessionFailure.unavailable }
                loop.plan.edit(live)
            }
        } catch {
            guard detailRequest == ticket else { return }
            await failed(error, identity: identity, ticket: ticket, detail: true)
        }
    }

    func back() async { detailRequest = UUID(); destination = nil; destinationError = nil; await refresh() }
    func dismissError() { destinationError = nil }

    private func failed(_ error: Error, identity: SessionSnapshot, ticket: UUID, detail: Bool) async {
        let snapshot = await controller.snapshot()
        guard (detail ? detailRequest : request) == ticket else { return }
        if snapshot != identity { bind(snapshot); sessionChanged?(snapshot); return }
        let message: String
        if case SessionFailure.rejected(let status, _) = error, status == 404 || status == 403 {
            message = detail ? "search.destination.unavailable" : "search.unavailable"
        } else { message = "search.error" }
        if detail { destinationError = message } else { errorKey = message }
    }

    private func persist() {
        guard let ownerID, let data = try? JSONEncoder().encode(origin) else { return }
        defaults.set(data, forKey: prefix + ownerID)
    }
}
