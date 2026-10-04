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
    private var searchPages = 0
    @Published var searchQuery = ""
    @Published var searchReturnAnchor: UUID?
    @Published private(set) var nextCursor: String?
    @Published private(set) var busy = false
    @Published private(set) var errorKey: String?
    @Published private var preparedInvitation: (householdId: UUID, value: HouseholdInvitation)?
    var invitation: HouseholdInvitation? { preparedInvitation?.householdId == selectedId ? preparedInvitation?.value : nil }
    private var reviewedInvitation: InviteSecret?
    @Published private(set) var invitationProblem: InvitationProblem?
    @Published private(set) var invitationPreview: HouseholdInvitationPreview?
    @Published private(set) var pending: PendingFinancialConfirmation?
    @Published var editor: HouseholdActivityEditor?
    @Published var showManagement = false { didSet { if !showManagement { joiningByInvitation = false } } }
    /// The join step is open over the current Household. Selection changes only when an accept succeeds.
    @Published private(set) var joiningByInvitation = false
    @Published private(set) var identity: SessionSnapshot?
    @Published var pendingInvitationToken = ""
    var addAccount: (() -> Void)?
    var navigateToAccounts: (() -> Void)?
    var sessionChanged: ((SessionSnapshot) -> Void)?
    var financialChanged: (() async -> Void)?
    lazy var plan = HouseholdPlanModel(household: self)
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
        lastSearchQuery = nil; searchQuery = ""; availability = .discovering; showManagement = false; errorKey = nil
        reviewedInvitation = nil; invitationProblem = nil; pendingInvitationToken = ""
        if let identity { pending = try? journal.pending(for: identity) }
    }
    func clear() {
        generation = UUID(); searchGeneration = UUID(); snapshot = nil; detail = nil; history = []; search = []; nextCursor = nil; editor = nil; highlightActivityId = nil; searchState = .idle
        searchQuery = ""; searchReturnAnchor = nil; searchPages = 0; plan.clear()
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
            await plan.refresh()
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
        searchReturnAnchor = hit.id
        if hit.kind == .plan, let ref = hit.planRef {
            await plan.open(ref, origin: .search)
        } else if hit.kind != .plan, let accountId = hit.accountId {
            await open(accountId)
            if detail?.account.account.id == accountId { highlightActivityId = hit.activityId }
        }
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
        lastSearchQuery = query; searchQuery = query; searchState = .loading
        var items = [URLQueryItem(name: "q", value: query)]
        if more, let nextCursor { items.append(URLQueryItem(name: "cursor", value: nextCursor)) }
        if !more { search = []; nextCursor = nil }
        do {
            let value = try await controller.householdResponse(HouseholdSearchPage.self, path: path(selectedId, "/search"), query: items, expectedIdentity: identity)
            guard current(ticket, identity), searchGeneration == searchTicket else { return }
            search = more ? search + value.items.filter { item in !search.contains(where: { $0.id == item.id }) } : value.items
            searchPages = more ? searchPages + 1 : 1
            nextCursor = value.nextCursor; searchState = search.isEmpty ? .empty : .results
        } catch {
            guard current(ticket, identity), searchGeneration == searchTicket else { return }
            searchState = .unavailable
            handleAccessFailure(error, householdId: selectedId)
        }
    }
    /// A pasted link, a scanned QR's link or a typed code previews the same invitation.
    func previewInvitation(_ input: String) async {
        guard isAvailable, let identity else { return }; let ticket = generation; invitationPreview = nil; invitationProblem = nil
        guard let secret = InviteSecret(input: input) else { invitationProblem = .invalid; return }
        do {
            let body = try JSONEncoder().encode(HouseholdCommand(secret: secret))
            let value = try await controller.householdResponse(HouseholdInvitationPreview.self, path: "/invitations/preview", method: "POST", body: body, expectedIdentity: identity)
            guard current(ticket, identity) else { return }; invitationPreview = value; reviewedInvitation = secret
        } catch {
            guard current(ticket, identity) else { return }
            let problem = InvitationProblem(error)
            if Self.invitationOutcomes.contains(problem) { invitationProblem = problem; return }
            await failed(error, ticket, identity, householdId: nil)
        }
    }
    func cancelInvitationReview() { invitationPreview = nil; reviewedInvitation = nil; invitationProblem = nil }
    func acceptInvitation(displayName: String) async {
        guard let reviewedInvitation else { errorKey = "household.changed"; return }
        await command(HouseholdCommand(secret: reviewedInvitation, displayName: displayName), path: "/invitations/accept")
    }
    /// Opens the join step for an invitation that arrived by link or by the beta gate.
    func beginJoin(_ input: String) async -> Bool {
        guard isAvailable else { return false }
        cancelInvitationReview()
        pendingInvitationToken = input; showManagement = true; joiningByInvitation = true
        return true
    }
    /// Answers about the invitation itself; anything else keeps the surface's own recovery.
    private static let invitationOutcomes: [InvitationProblem] = [.invalid, .expired, .revoked, .used, .rateLimited]
    func command(_ command: HouseholdCommand, path: String, method: String = "POST") async {
        guard isAvailable, let identity, let owner = identity.profile.flatMap({ UUID(uuidString: $0.id) }), !busy, pending == nil else { return }
        if path == "/invitations/accept", (command.token.map(InviteSecret.token) ?? command.code.map(InviteSecret.code)) != reviewedInvitation { errorKey = "household.changed"; return }
        do {
            let write = PendingFinancialConfirmation(ownerId: owner, originAccountId: nil, route: "households", path: path, method: method, body: try JSONEncoder().encode(command), key: UUID(), householdMembershipId: household?.membershipId, householdAuthorizationVersion: household?.version, householdOperation: .management)
            try journal.begin(write, for: identity); pending = write
            await retry()
        } catch { errorKey = "household.storageError" }
    }
    func retry() async {
        guard isAvailable, let identity, let write = pending, !busy else { return }
        let operation = operation(write)
        if case .plan(let id, _) = operation {
            guard selectedId == id, household?.membershipId == write.householdMembershipId else { errorKey = "sharedPlan.changed"; return }
        }
        let ticket = generation; let attempt = UUID()
        writeAttempt = attempt; busy = true; errorKey = nil
        defer { if writeAttempt == attempt { busy = false; writeAttempt = nil } }
        do {
            guard write.route == "households" else { throw SessionFailure.invalidResponse }
            switch operation {
            case .plan:
                let value = try await controller.sendHouseholdPlanConfirmation(write, expectedIdentity: identity)
                guard current(ticket, identity) else { return }
                plan.writeResolved(value)
            case .activity:
                let _: HouseholdReceipt = try await send(write, identity)
            case .management:
                let value: HouseholdMutation = try await send(write, identity)
                guard current(ticket, identity) else { return }
                if write.path == "" || write.path == "/invitations/accept" {
                    joiningByInvitation = false
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
            busy = false
            if case .plan = operation {
                let query = lastSearchQuery; let anchor = searchReturnAnchor; let pages = searchPages
                await refresh()
                guard current(ticket, identity) else { return }
                if let query {
                    await refreshSearch(query, pages: pages)
                    searchReturnAnchor = anchor
                }
                await financialChanged?()
            } else {
                clear(); await refresh()
                if case .activity = operation, let query = lastSearchQuery { await find(query) }
            }
        } catch {
            guard current(ticket, identity) else { return }
            let accessFailure: Bool
            if case .plan(let id, _) = operation { accessFailure = await handlePlanAccessFailure(error, householdId: id) }
            else { accessFailure = handleAccessFailure(error, householdId: requestHouseholdId(write.path)) }
            guard current(ticket, identity) else { return }
            if availability != .disabled {
                if write.path == "/invitations/accept", Self.invitationOutcomes.contains(InvitationProblem(error)) { invitationProblem = InvitationProblem(error) }
                if case SessionFailure.rejected(let status, _) = error, status >= 400 && status < 500 && status != 429 {
                    try? journal.clear(write, for: identity); pending = nil
                    if !accessFailure {
                        if case .plan = operation {
                            plan.sheet = nil
                            await refresh()
                            if current(ticket, identity) { errorKey = HouseholdPlanModel.message(error) }
                        } else {
                            let explained = invitationProblem != nil && write.path == "/invitations/accept"
                            clear()
                            if write.path == "/invitations/accept", selectedId != nil { await refresh() }
                            if current(ticket, identity) || write.path == "/invitations/accept" { errorKey = explained ? nil : "household.changed" }
                        }
                    }
                } else { errorKey = "household.uncertain" }
            }
            let latest = await controller.snapshot()
            if latest.revision != identity.revision || latest.phase != .authenticated { bind(latest); sessionChanged?(latest) }
        }
    }
    private func refreshSearch(_ query: String, pages: Int) async {
        guard isAvailable, let identity, let selectedId else { return }
        let ticket = generation; let searchTicket = UUID(); searchGeneration = searchTicket
        var refreshed: [HouseholdSearchHit] = []; var cursor: String?
        do {
            for page in 0..<max(1, pages) {
                var items = [URLQueryItem(name: "q", value: query)]
                if let cursor { items.append(URLQueryItem(name: "cursor", value: cursor)) }
                let value = try await controller.householdResponse(HouseholdSearchPage.self, path: path(selectedId, "/search"), query: items, expectedIdentity: identity)
                guard current(ticket, identity), searchGeneration == searchTicket else { return }
                refreshed += value.items.filter { item in !refreshed.contains { $0.id == item.id } }
                cursor = value.nextCursor
                if cursor == nil || page == max(1, pages) - 1 { break }
            }
            // Publish the complete refreshed window together, keeping the
            // mounted ScrollView's content height stable during every read.
            search = refreshed; nextCursor = cursor; searchState = refreshed.isEmpty ? .empty : .results
        } catch {
            guard current(ticket, identity), searchGeneration == searchTicket else { return }
            searchState = .unavailable; handleAccessFailure(error, householdId: selectedId)
        }
    }
    private func send<Value: Decodable & Sendable>(_ write: PendingFinancialConfirmation, _ identity: SessionSnapshot) async throws -> Value {
        if case .activity(let id, _) = operation(write) {
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
            let write = PendingFinancialConfirmation(ownerId: owner, originAccountId: body.accountId ?? body.sourceAccountId, route: "households", path: path(household.id, "/activities" + (activityId.map { "/" + $0.uuidString } ?? "")), method: activityId == nil ? "POST" : "PATCH", body: try JSONEncoder().encode(HouseholdFinancialCommand(membershipId: membership, expectedVersion: version, activity: body)), key: UUID(), householdMembershipId: membership, householdAuthorizationVersion: version, householdOperation: .activity(householdId: household.id, activityId: activityId))
            try journal.begin(write, for: identity); pending = write; await retry()
        } catch { errorKey = "household.storageError" }
    }
    func confirmPlan(body: Data, scope: HouseholdPlanScope, action: HouseholdPlanAction) async throws {
        guard isAvailable, let identity, let owner = identity.profile.flatMap({ UUID(uuidString: $0.id) }), let household,
              household.membershipId == scope.membershipId, household.version == scope.authorizationVersion, pending == nil, !busy else { throw SessionFailure.staleOperation }
        let write = PendingFinancialConfirmation(ownerId: owner, originAccountId: nil, route: "households", path: path(household.id, "/plan" + action.path), method: action.method, body: body, key: UUID(), householdMembershipId: scope.membershipId, householdAuthorizationVersion: scope.authorizationVersion, householdOperation: .plan(householdId: household.id, action: action))
        try journal.begin(write, for: identity); pending = write; await retry()
    }
    private func operation(_ write: PendingFinancialConfirmation) -> HouseholdWriteOperation {
        write.householdOperation ?? .management
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
    // A plan's uniform not-found response also covers a removed definition or
    // claim. Verify the Household boundary before discarding its Search context.
    func handlePlanAccessFailure(_ error: Error, householdId: UUID) async -> Bool {
        guard case SessionFailure.rejected(404, "household_not_found") = error else { return handleAccessFailure(error, householdId: householdId) }
        guard let identity, let household, household.id == householdId else { return true }
        let ticket = generation
        do {
            let value = try await controller.householdResponse(Household.self, path: path(householdId), expectedIdentity: identity)
            guard current(ticket, identity), selectedId == householdId else { return true }
            guard value.id == householdId, value.membershipId == household.membershipId, value.version == household.version else {
                suspend(.unavailable); errorKey = "sharedPlan.changed"; return true
            }
            return false
        } catch {
            guard current(ticket, identity) else { return true }
            if !handleAccessFailure(error, householdId: householdId) { errorKey = "household.loadError" }
            return true
        }
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
