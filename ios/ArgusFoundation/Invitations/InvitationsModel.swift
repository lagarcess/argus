import SwiftUI
import ArgusSession

/// Beta admission and the invitations a person sends. Household membership stays with
/// `HouseholdModel` and account access with its grants; nothing here infers either one.
@MainActor
final class InvitationsModel: ObservableObject {
    enum Admission: Equatable {
        case checking
        /// The invites surface is off on this server: today's app, unchanged.
        case surfaceOff
        /// The access check failed; the server gate is advisory, so the app stays usable.
        case unknown
        case admitted
        case required
    }

    enum Notice: Identifiable, Equatable {
        case alreadyAdmitted, secretsShownOnce, householdUnavailable
        case problem(InvitationProblem)
        var id: String { String(describing: self) }
    }

    @Published private(set) var identity: SessionSnapshot?
    @Published private(set) var admission = Admission.checking
    @Published private(set) var access: BetaAccess?
    @Published var gate = ReleaseInviteGateState.ready
    @Published var gateCode = ""
    @Published private(set) var pendingLink: InviteSecret?
    @Published var notice: Notice?
    @Published private(set) var personal = ReleasePersonalInvitationState.loading
    @Published private(set) var sent: [SentInvite] = []
    /// Nil until the server answers the founder-only list; a refusal keeps it nil.
    @Published private(set) var groupLinks: [GroupLink]?
    @Published private(set) var group = ReleaseGroupInvitationState.draft

    let universalLinksEnabled: Bool
    var openHousehold: ((String) async -> Bool)?
    private let clientFor: (SessionSnapshot) -> InvitesClient
    private var generation = UUID()
    private var continuing = false
    private var createKey: UUID?
    private var groupKey: UUID?
    private var personalShare: ReleaseInvitationShare?
    private var groupShare: (id: UUID, share: ReleaseInvitationShare)?

    init(universalLinksEnabled: Bool, clientFor: @escaping (SessionSnapshot) -> InvitesClient) {
        self.universalLinksEnabled = universalLinksEnabled
        self.clientFor = clientFor
    }

    static func universalLinksEnabled(bundle: Bundle = .main) -> Bool {
        let value = bundle.object(forInfoDictionaryKey: "ARGUS_INVITE_UNIVERSAL_LINK_ENABLED")
        return value as? Bool == true || (value as? String)?.lowercased() == "true"
    }

    var showsInvitations: Bool { admission == .admitted || admission == .unknown }

    func bind(_ next: SessionSnapshot?) {
        let signedIn = next?.phase == .authenticated ? next : nil
        guard signedIn?.revision != identity?.revision || signedIn?.profile?.id != identity?.profile?.id else { return }
        identity = signedIn; generation = UUID()
        admission = .checking; access = nil; gate = .ready; gateCode = ""; notice = nil
        personal = .loading; sent = []; groupLinks = nil; group = .draft
        createKey = nil; groupKey = nil; personalShare = nil; groupShare = nil
    }

    // MARK: Beta admission

    func refreshAccess() async {
        guard let identity else { return }
        let ticket = generation
        do {
            let value = try await clientFor(identity).access()
            guard ticket == generation else { return }
            access = value
            admission = value.admitted ? .admitted : .required
        } catch {
            guard ticket == generation else { return }
            admission = InvitationProblem(error) == .surfaceUnavailable ? .surfaceOff : .unknown
        }
        await continuePendingLink()
    }

    func submitCode(_ input: String) async {
        guard let secret = InviteSecret(input: input) else { gate = .invalid; return }
        await redeem(secret)
    }

    private func redeem(_ secret: InviteSecret) async {
        guard let identity else { return }
        let ticket = generation
        gate = .checking
        do {
            _ = try await clientFor(identity).redeem(secret)
            guard ticket == generation else { return }
            pendingLink = nil; gateCode = ""; gate = .ready
            await refreshAccess()
        } catch {
            guard ticket == generation else { return }
            switch InvitationProblem(error) {
            case .householdInvitation:
                pendingLink = nil; gate = .ready
                await handToHousehold(secret)
            case .surfaceUnavailable:
                gate = .ready; admission = .surfaceOff
            case let problem:
                gate = Self.gateState(problem)
            }
        }
    }

    static func gateState(_ problem: InvitationProblem) -> ReleaseInviteGateState {
        switch problem {
        case .invalid: .invalid
        case .expired: .expired
        case .revoked: .revoked
        case .used: .consumed
        case .full: .full
        case .rateLimited: .rateLimited
        case .invitationRequired: .waitlist
        default: .unavailable
        }
    }

    // MARK: Links

    /// Keeps the link's intent until sign-in and the access check finish. Returns false for foreign links.
    @discardableResult
    func open(_ url: URL) -> Bool {
        guard let token = InvitationLink.token(in: url) else { return false }
        if InvitationLink.isUniversal(url) && !universalLinksEnabled { return false }
        pendingLink = .token(token)
        if identity != nil && admission != .checking { Task { await continuePendingLink() } }
        return true
    }

    func discardPendingLink() { pendingLink = nil }

    func continuePendingLink() async {
        guard let secret = pendingLink, let identity, !continuing else { return }
        continuing = true
        defer { continuing = false }
        switch admission {
        case .checking:
            return
        case .required:
            await redeem(secret)
        case .surfaceOff:
            pendingLink = nil
            await handToHousehold(secret)
        case .admitted, .unknown:
            let ticket = generation
            do {
                let preview = try await clientFor(identity).preview(secret)
                guard ticket == generation else { return }
                pendingLink = nil
                if preview.kind == .household { await handToHousehold(secret) } else { notice = .alreadyAdmitted }
            } catch {
                guard ticket == generation else { return }
                pendingLink = nil
                let problem = InvitationProblem(error)
                if problem == .surfaceUnavailable { await handToHousehold(secret) } else { notice = .problem(problem) }
            }
        }
    }

    private func handToHousehold(_ secret: InviteSecret) async {
        let input: String
        switch secret { case .token(let value): input = value; case .code(let value): input = value }
        if await openHousehold?(input) != true { notice = .householdUnavailable }
    }

    // MARK: Personal invitations

    func loadPersonal() async {
        guard let identity else { return }
        let ticket = generation
        do {
            let value = try await clientFor(identity).sent()
            guard ticket == generation else { return }
            sent = value.invitations
            personal = .ready(remaining: value.quota.remaining, total: value.quota.limit, invitation: personalShare)
        } catch {
            guard ticket == generation else { return }
            personal = .unavailable
        }
    }

    func createPersonal() async {
        guard let identity else { return }
        let ticket = generation
        let key = createKey ?? UUID()
        createKey = key
        personal = .loading
        do {
            let value = try await clientFor(identity).createInvite(key: key)
            guard ticket == generation else { return }
            createKey = nil
            personalShare = value.invitation.hasSecrets ? share(value.invitation) : nil
            if !value.invitation.hasSecrets { notice = .secretsShownOnce }
        } catch {
            guard ticket == generation else { return }
            let problem = InvitationProblem(error)
            // Only a definite answer retires the key; a lost response retries the same create.
            if problem != .unavailable { createKey = nil }
            if problem != .quotaExhausted { notice = .problem(problem) }
        }
        await loadPersonal()
    }

    // MARK: Founder group links

    func loadGroupLinks() async {
        guard let identity else { return }
        let ticket = generation
        do {
            let links = try await clientFor(identity).groupLinks()
            guard ticket == generation else { return }
            groupLinks = links
            if let groupShare, let link = links.first(where: { $0.id == groupShare.id }) {
                group = .ready(cap: link.cap, used: link.redeemed, invitation: groupShare.share)
            }
        } catch {
            guard ticket == generation else { return }
            groupLinks = nil
        }
    }

    func startGroupLink() { if case .ready = group { group = .draft }; groupShare = nil }

    func createGroupLink(label: String, cap: Int, expiresAt: Date) async {
        guard let identity else { return }
        let ticket = generation
        let key = groupKey ?? UUID()
        groupKey = key
        group = .creating
        do {
            let value = try await clientFor(identity).createGroupLink(label: label, cap: cap, expiresAt: expiresAt, key: key)
            guard ticket == generation else { return }
            groupKey = nil
            if value.invitation.hasSecrets {
                let share = share(value.invitation)
                groupShare = (value.invitation.id, share)
                group = .ready(cap: value.invitation.cap ?? cap, used: 0, invitation: share)
            } else {
                group = .draft; notice = .secretsShownOnce
            }
        } catch {
            guard ticket == generation else { return }
            let problem = InvitationProblem(error)
            if problem != .unavailable { groupKey = nil }
            group = .draft; notice = .problem(problem)
        }
        await loadGroupLinks()
    }

    func revokeGroupLink(_ id: UUID) async {
        guard let identity else { return }
        let ticket = generation
        do { try await clientFor(identity).revokeGroupLink(id) }
        catch { if ticket == generation { notice = .problem(InvitationProblem(error)) } }
        await loadGroupLinks()
    }

    private func share(_ invite: CreatedInvite) -> ReleaseInvitationShare {
        ReleaseInvitationShare(url: invite.link, code: invite.code, expiresAt: invite.expiresAt, testFlightURL: access?.testFlightURL)
    }
}
