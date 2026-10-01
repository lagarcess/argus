import SwiftUI
import ArgusSession

@MainActor
final class HouseholdModel: ObservableObject {
    enum Availability { case discovering, available, disabled, unavailable }
    @Published private(set) var availability = Availability.discovering
    @Published private(set) var households: [Household] = []
    @Published private(set) var selectedId: UUID?
    @Published private(set) var household: Household?
    @Published private(set) var snapshot: HouseholdSnapshot?
    @Published private(set) var detail: HouseholdAccountDetail?
    @Published private(set) var history: [HouseholdActivity] = []
    @Published private(set) var search: [HouseholdSearchHit] = []
    enum SearchState { case idle, loading, results, empty, unavailable }
    @Published private(set) var searchState = SearchState.idle
    @Published private(set) var highlightActivityId: UUID?
    private var lastSearchQuery: String?
    @Published private(set) var nextCursor: String?
    @Published private(set) var busy = false
    @Published private(set) var errorKey: String?
    @Published private var preparedInvitation: (householdId: UUID, value: HouseholdInvitation)?
    var invitation: HouseholdInvitation? { preparedInvitation?.householdId == selectedId ? preparedInvitation?.value : nil }
    private var reviewedInvitationToken: String?
    @Published private(set) var invitationPreview: HouseholdInvitationPreview?
    @Published private(set) var pending: PendingFinancialConfirmation?
    @Published var editor: HouseholdActivityEditor?
    @Published var showManagement = false
    @Published private(set) var identity: SessionSnapshot?
    @Published var pendingInvitationToken = ""
    var addAccount: (() -> Void)?
    var navigateToAccounts: (() -> Void)?
    var sessionChanged: ((SessionSnapshot) -> Void)?
    let controller: SessionController
    let journal: FinancialWriteJournal
    private let storagePrefix: String
    private var writeAttempt: UUID?
    private var generation = UUID()
    private var searchGeneration = UUID()

    init(controller: SessionController, configuration: SessionConfiguration, journal: FinancialWriteJournal? = nil) {
        self.controller = controller; storagePrefix = configuration.storagePrefix + ".household.selection."
        self.journal = journal ?? FinancialWriteJournal(configuration: configuration, namespace: ".household")
    }
    var isAvailable: Bool { availability == .available }
    var active: Bool { isAvailable && selectedId != nil }
    private var storageKey: String? { identity?.profile.map { storagePrefix + $0.id } }

    func bind(_ next: SessionSnapshot?) {
        guard next?.revision != identity?.revision || next?.profile?.id != identity?.profile?.id || next?.phase != identity?.phase else { return }
        identity = next?.phase == .authenticated ? next : nil
        clear(); households = []; household = nil; preparedInvitation = nil; invitationPreview = nil; pending = nil; busy = false; writeAttempt = nil
        selectedId = storageKey.flatMap { UserDefaults.standard.string(forKey: $0) }.flatMap(UUID.init(uuidString:))
        lastSearchQuery = nil; availability = .discovering; showManagement = false; errorKey = nil
        reviewedInvitationToken = nil; pendingInvitationToken = ""
        if let identity { pending = try? journal.pending(for: identity) }
    }
    func clear() {
        generation = UUID(); searchGeneration = UUID(); snapshot = nil; detail = nil; history = []; search = []; nextCursor = nil; editor = nil; highlightActivityId = nil; searchState = .idle
    }
    func select(_ id: UUID?) async {
        guard isAvailable else { return }
        clear(); selectedId = id; household = nil; preparedInvitation = nil; errorKey = nil
        if let storageKey { UserDefaults.standard.set(id?.uuidString, forKey: storageKey) }
        await refresh()
    }
    func refresh() async {
        guard let identity else { return }
        let ticket = generation; let requestedHousehold = selectedId
        do {
            let result = try await controller.householdResponse(HouseholdList.self, expectedIdentity: identity)
            guard current(ticket, identity) else { return }
            households = result.households
            guard let selectedId else { availability = .available; errorKey = nil; return }
            guard let h = households.first(where: { $0.id == selectedId }) else {
                accessEnded(); return
            }
            let values = try await controller.householdResponse(HouseholdSnapshot.self, path: path(selectedId, "/snapshot"), expectedIdentity: identity)
            guard current(ticket, identity) else { return }
            guard h.membershipId == values.membershipId, h.version == values.authorizationVersion else { suspend(.unavailable); errorKey = "household.changed"; return }
            if snapshot?.authorizationVersion != values.authorizationVersion || snapshot?.membershipId != values.membershipId {
                clear()
            }
            household = h; snapshot = values; availability = .available; errorKey = nil
        } catch { await failed(error, ticket, identity, householdId: requestedHousehold, discovery: true) }
    }
    func foreground() async { clear(); await refresh() }
    func open(_ id: UUID) async {
        guard isAvailable, let identity, let selectedId else { return }
        let ticket = generation
        detail = nil; history = []
        do {
            let value = try await controller.householdResponse(HouseholdAccountDetail.self, path: path(selectedId, "/accounts/" + id.uuidString), expectedIdentity: identity)
            guard current(ticket, identity) else { return }; detail = value
        } catch { await failed(error, ticket, identity, householdId: selectedId) }
    }
    func back() { detail = nil; history = []; highlightActivityId = nil }
    func openSearchHit(_ hit: HouseholdSearchHit) async {
        await open(hit.accountId)
        if detail?.account.account.id == hit.accountId { highlightActivityId = hit.activityId }
    }
    func loadHistory(_ id: UUID) async {
        guard isAvailable, let identity, let selectedId else { return }; let ticket = generation
        do {
            let value = try await controller.householdResponse(HouseholdHistory.self, path: path(selectedId, "/activities/" + id.uuidString + "/history"), expectedIdentity: identity)
            guard current(ticket, identity) else { return }; history = value.items
        } catch { await failed(error, ticket, identity, householdId: selectedId) }
    }
    func find(_ query: String, more: Bool = false) async {
        guard isAvailable, let identity, let selectedId else { return }
        let ticket = generation; let searchTicket = UUID(); searchGeneration = searchTicket
        lastSearchQuery = query; searchState = .loading
        var items = [URLQueryItem(name: "q", value: query)]
        if more, let nextCursor { items.append(URLQueryItem(name: "cursor", value: nextCursor)) }
        if !more { search = []; nextCursor = nil }
        do {
            let value = try await controller.householdResponse(HouseholdSearchPage.self, path: path(selectedId, "/search"), query: items, expectedIdentity: identity)
            guard current(ticket, identity), searchGeneration == searchTicket else { return }
            search = more ? search + value.items.filter { item in !search.contains(where: { $0.id == item.id }) } : value.items
            nextCursor = value.nextCursor; searchState = search.isEmpty ? .empty : .results
        } catch {
            guard current(ticket, identity), searchGeneration == searchTicket else { return }
            searchState = .unavailable
            handleAccessFailure(error, householdId: selectedId)
        }
    }
    func previewInvitation(_ token: String) async {
        guard isAvailable, let identity else { return }; let ticket = generation; invitationPreview = nil
        do {
            let body = try JSONEncoder().encode(HouseholdCommand(token: Self.token(token)))
            let value = try await controller.householdResponse(HouseholdInvitationPreview.self, path: "/invitations/preview", method: "POST", body: body, expectedIdentity: identity)
            guard current(ticket, identity) else { return }; invitationPreview = value; reviewedInvitationToken = Self.token(token)
        } catch { await failed(error, ticket, identity, householdId: nil) }
    }
    func cancelInvitationReview() { invitationPreview = nil; reviewedInvitationToken = nil }
    static func token(_ input: String) -> String {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        return URLComponents(string: trimmed)?.fragment ?? trimmed
    }
    func command(_ command: HouseholdCommand, path: String, method: String = "POST") async {
        guard isAvailable, let identity, let owner = identity.profile.flatMap({ UUID(uuidString: $0.id) }), !busy, pending == nil else { return }
        if path == "/invitations/accept", command.token != reviewedInvitationToken { errorKey = "household.changed"; return }
        do {
            let write = PendingFinancialConfirmation(ownerId: owner, originAccountId: nil, route: "households", path: path, method: method, body: try JSONEncoder().encode(command), key: UUID(), householdMembershipId: household?.membershipId, householdAuthorizationVersion: household?.version)
            try journal.begin(write, for: identity); pending = write
            await retry()
        } catch { errorKey = "household.storageError" }
    }
    func retry() async {
        guard isAvailable, let identity, let write = pending, !busy else { return }
        let ticket = generation; let attempt = UUID()
        writeAttempt = attempt; busy = true; errorKey = nil
        defer { if writeAttempt == attempt { busy = false; writeAttempt = nil } }
        do {
            guard write.route == "households" else { throw SessionFailure.invalidResponse }
            if write.path.contains("/activities") {
                let _: HouseholdReceipt = try await send(write, identity)
            } else {
                let value: HouseholdMutation = try await send(write, identity)
                guard current(ticket, identity) else { return }
                if write.path == "" || write.path == "/invitations/accept" {
                    if value.state == "active" { selectedId = value.householdId }
                    else { errorKey = "household.accessEnded" }
                }
                if let invitation = value.invitation, selectedId == value.householdId {
                    preparedInvitation = (value.householdId, invitation)
                }
            }
            guard current(ticket, identity) else { return }
            try journal.clear(write, for: identity); pending = nil; editor = nil
            if let storageKey { UserDefaults.standard.set(selectedId?.uuidString, forKey: storageKey) }
            busy = false; clear(); await refresh()
            if write.path.contains("/activities"), let query = lastSearchQuery { await find(query) }
        } catch {
            guard current(ticket, identity) else { return }
            let accessFailure = handleAccessFailure(error, householdId: requestHouseholdId(write.path))
            if availability != .disabled {
                if case SessionFailure.rejected(let status, _) = error, status >= 400 && status < 500 && status != 429 {
                    try? journal.clear(write, for: identity); pending = nil
                    if !accessFailure { clear(); errorKey = "household.changed" }
                } else { errorKey = "household.uncertain" }
            }
            let latest = await controller.snapshot()
            if latest.revision != identity.revision || latest.phase != .authenticated { bind(latest); sessionChanged?(latest) }
        }
    }
    private func send<Value: Decodable & Sendable>(_ write: PendingFinancialConfirmation, _ identity: SessionSnapshot) async throws -> Value {
        if write.path.contains("/activities"), let id = requestHouseholdId(write.path) {
            let value = try await controller.householdResponse(Household.self, path: path(id), expectedIdentity: identity)
            guard value.membershipId == write.householdMembershipId else { throw SessionFailure.rejected(status: 404, code: "household_access_unavailable") }
        }
        return try await controller.householdResponse(Value.self, path: write.path, method: write.method, body: write.body, key: write.key, expectedIdentity: identity)
    }
    func versionCommand(_ suffix: String, method: String = "POST", member: UUID? = nil, recipients: [HouseholdRecipient]? = nil) async {
        guard let household else { return }
        await command(HouseholdCommand(expectedVersion: household.version, userId: member, recipients: recipients), path: path(household.id, suffix), method: method)
    }
    func beginActivity(_ account: HouseholdAccount, correction: HouseholdActivity? = nil) {
        guard isAvailable, account.permission == "edit", let identity, let household, let snapshot, pending == nil else { return }
        editor = HouseholdActivityEditor(model: self, identity: identity, household: household, snapshot: snapshot, account: account, correction: correction)
    }
    func confirmActivity(_ body: FinancialActivityCommand, activityId: UUID?, membership: UUID, version: Int) async {
        guard isAvailable, let identity, let owner = identity.profile.flatMap({ UUID(uuidString: $0.id) }), let household, household.membershipId == membership, household.version == version, pending == nil else { return }
        do {
            let write = PendingFinancialConfirmation(ownerId: owner, originAccountId: body.accountId ?? body.sourceAccountId, route: "households", path: path(household.id, "/activities" + (activityId.map { "/" + $0.uuidString } ?? "")), method: activityId == nil ? "POST" : "PATCH", body: try JSONEncoder().encode(HouseholdFinancialCommand(membershipId: membership, expectedVersion: version, activity: body)), key: UUID(), householdMembershipId: membership, householdAuthorizationVersion: version)
            try journal.begin(write, for: identity); pending = write; await retry()
        } catch { errorKey = "household.storageError" }
    }
    private func requestHouseholdId(_ path: String) -> UUID? {
        path.split(separator: "/").first.flatMap { UUID(uuidString: String($0)) }
    }
    func path(_ id: UUID, _ suffix: String = "") -> String { "/" + id.uuidString + suffix }
    func current(_ ticket: UUID, _ session: SessionSnapshot) -> Bool { ticket == generation && identity?.revision == session.revision && identity?.profile?.id == session.profile?.id }
    func accessEnded() {
        availability = .available
        clear(); household = nil; selectedId = nil; preparedInvitation = nil
        showManagement = false; cancelInvitationReview(); pendingInvitationToken = ""
        if let storageKey { UserDefaults.standard.removeObject(forKey: storageKey) }
        errorKey = "household.accessEnded"
    }
    // Surface availability is server-owned; a disabled route says nothing about membership.
    @discardableResult
    func handleAccessFailure(_ error: Error, householdId: UUID?) -> Bool {
        guard case SessionFailure.rejected(_, let code) = error else { return false }
        switch code {
        case "households_unavailable": suspend(.disabled)
        case "household_not_found", "not_a_member", "household_closed", "household_access_unavailable":
            if let householdId, householdId == selectedId { accessEnded() }
            else { errorKey = "household.changed" }
        default: return false
        }
        return true
    }
    private func suspend(_ state: Availability) {
        clear(); lastSearchQuery = nil; availability = state; households = []; household = nil; preparedInvitation = nil
        showManagement = false; cancelInvitationReview(); pendingInvitationToken = ""
        errorKey = state == .unavailable ? "household.loadError" : nil
        // Keep actor-partitioned selection and exact pending bytes for explicit recovery.
    }
    private func failed(_ error: Error, _ ticket: UUID, _ session: SessionSnapshot, householdId: UUID?, discovery: Bool = false) async {
        guard current(ticket, session) else { return }
        if !handleAccessFailure(error, householdId: householdId) {
            if discovery { suspend(.unavailable) }
            else { errorKey = "household.loadError" }
        }
        let latest = await controller.snapshot()
        if latest.revision != session.revision || latest.phase != .authenticated { bind(latest); sessionChanged?(latest) }
    }
}
