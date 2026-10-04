#if DEBUG
import SwiftUI
import ArgusSession

/// Answers `/api/v1/invites` with the shapes in docs/api/openapi.yaml so UI tests drive the connected
/// screens and `InvitationsModel` without a server. It never grants real access.
actor InvitationsStubServer: InvitesTransport {
    struct Scenario {
        var surfaceOn = true, gateEnabled = true, admitted = false, founder = false, waitlist = true
        var quotaUsed = 3
        init(arguments: [String]) {
            surfaceOn = !arguments.contains("--harness-surface-off")
            gateEnabled = !arguments.contains("--harness-gate-off")
            admitted = arguments.contains("--harness-admitted")
            founder = arguments.contains("--harness-founder")
            waitlist = !arguments.contains("--harness-no-waitlist")
            if let index = arguments.firstIndex(of: "--harness-quota-used"), index + 1 < arguments.count { quotaUsed = Int(arguments[index + 1]) ?? 3 }
        }
    }
    private var scenario: Scenario
    private var sent: [[String: Any]] = []
    private var links: [[String: Any]]
    private let limit = 10

    init(scenario: Scenario) {
        self.scenario = scenario
        let soon = InvitationDates.string(Date().addingTimeInterval(86_400 * 20))
        let past = InvitationDates.string(Date().addingTimeInterval(-86_400))
        links = [
            Self.link(label: "Launch dinner", cap: 25, redeemed: 25, overflow: 3, expires: soon, state: "full"),
            Self.link(label: "Santo Domingo meetup", cap: 40, redeemed: 12, overflow: 0, expires: past, state: "expired"),
        ]
        sent = [
            ["id": UUID().uuidString, "kind": "beta", "invitation_id": UUID().uuidString, "state": "accepted",
             "sent_at": past, "expires_at": soon, "accepted_at": InvitationDates.string(Date())],
            ["id": UUID().uuidString, "kind": "household", "invitation_id": UUID().uuidString, "state": "pending",
             "sent_at": past, "expires_at": soon, "accepted_at": NSNull()],
        ]
    }

    func send(route: String, path: String, method: String, body: Data?, key: String?) async throws -> Data {
        guard route == "invites", scenario.surfaceOn else { throw SessionFailure.rejected(status: 404, code: "invites_unavailable") }
        let fields = body.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } ?? [:]
        let secret = (fields["code"] ?? fields["token"]) as? String ?? ""
        switch (method, path) {
        case ("GET", "/access"):
            return try json(["gate_enabled": scenario.gateEnabled, "admitted": scenario.admitted || !scenario.gateEnabled,
                             "waitlist_url": scenario.waitlist ? "https://cuadrao.ai" : NSNull(),
                             "testflight_url": "https://testflight.apple.com/join/EXAMPLE0"])
        case ("GET", ""):
            return try json(["quota": quota(), "invitations": sent])
        case ("POST", ""):
            guard scenario.quotaUsed < limit else { throw SessionFailure.rejected(status: 409, code: "beta_invite_quota_exhausted") }
            scenario.quotaUsed += 1
            let expires = InvitationDates.string(Date().addingTimeInterval(86_400 * 7))
            sent.insert(["id": UUID().uuidString, "kind": "beta", "invitation_id": UUID().uuidString, "state": "pending",
                         "sent_at": InvitationDates.string(Date()), "expires_at": expires, "accepted_at": NSNull()], at: 0)
            return try json(["invitation": ["id": UUID().uuidString, "kind": "beta", "expires_at": expires,
                                            "token": "harness-only-not-a-real-token-000000000000", "code": "DEMO-ONLY-0007",
                                            "link": "https://cuadrao.ai/invite#harness-only-not-a-real-token-000000000000",
                                            "source_label": NSNull(), "cap": NSNull(), "replayed": false] as [String: Any],
                             "quota": quota()])
        case ("POST", "/preview"):
            if secret.contains("household") || secret.hasPrefix("HOME") {
                return try json(["kind": "household", "available": true, "expires_at": InvitationDates.string(Date().addingTimeInterval(86_400)), "household_name": "Casa"])
            }
            try outcome(secret)
            return try json(["kind": "beta", "available": true, "expires_at": InvitationDates.string(Date().addingTimeInterval(86_400)), "household_name": NSNull()])
        case ("POST", "/redeem"):
            if secret.contains("household") || secret.hasPrefix("HOME") {
                throw SessionFailure.rejected(status: 409, code: "household_invitation_requires_accept")
            }
            try outcome(secret)
            let outcome = scenario.admitted ? "already_admitted" : "admitted"
            scenario.admitted = true
            return try json(["admitted": true, "outcome": outcome, "kind": "beta", "replayed": false])
        case ("GET", "/group-links"):
            guard scenario.founder else { throw SessionFailure.rejected(status: 403, code: "founder_required") }
            return try json(["links": links])
        case ("POST", "/group-links"):
            guard scenario.founder else { throw SessionFailure.rejected(status: 403, code: "founder_required") }
            let label = fields["source_label"] as? String ?? ""
            let cap = fields["cap"] as? Int ?? 0
            let expires = fields["expires_at"] as? String ?? ""
            let id = UUID().uuidString
            links.insert(Self.link(id: id, label: label, cap: cap, redeemed: 0, overflow: 0, expires: expires, state: "open"), at: 0)
            return try json(["invitation": ["id": id, "kind": "group_link", "expires_at": expires,
                                            "token": "harness-only-group-token-0000000000000000", "code": "DEMO-ONLY-GRP1",
                                            "link": "https://cuadrao.ai/invite#harness-only-group-token-0000000000000000",
                                            "source_label": label, "cap": cap, "replayed": false] as [String: Any],
                             "quota": NSNull()])
        default:
            throw SessionFailure.rejected(status: 404, code: "not_found")
        }
    }

    /// Codes the UI tests type for each server outcome; anything else names no invitation.
    private func outcome(_ secret: String) throws {
        let upper = secret.uppercased()
        if upper.hasPrefix("BETA") || secret.contains("beta-link") { return }
        let failures: [(String, Int, String)] = [
            ("EXPD", 409, "invitation_expired"), ("USED", 409, "invitation_consumed"), ("REVK", 409, "invitation_revoked"),
            ("FULL", 409, "group_link_full"), ("WAIT", 429, "invite_rate_limited"), ("DOWN", 503, "invite_codes_unavailable"),
        ]
        for (prefix, status, code) in failures where upper.hasPrefix(prefix) || secret.lowercased().contains(prefix.lowercased() + "-link") {
            throw SessionFailure.rejected(status: status, code: code)
        }
        throw SessionFailure.rejected(status: 404, code: "invitation_not_found")
    }

    private func quota() -> [String: Any] { ["limit": limit, "used": scenario.quotaUsed, "remaining": max(0, limit - scenario.quotaUsed)] }
    private func json(_ value: [String: Any]) throws -> Data { try JSONSerialization.data(withJSONObject: value) }
    private static func link(id: String = UUID().uuidString, label: String, cap: Int, redeemed: Int, overflow: Int, expires: String, state: String) -> [String: Any] {
        ["id": id, "source_label": label, "cap": cap, "redeemed": redeemed, "overflow": overflow, "expires_at": expires, "revoked_at": NSNull(), "state": state]
    }
}

/// `--invitations-harness`: the connected invitation screens over the stub server, with a stand-in sign-in.
struct InvitationsHarness: View {
    @StateObject private var model: InvitationsModel
    @State private var signedIn: Bool
    @State private var householdInput: String?
    private let arguments = ProcessInfo.processInfo.arguments

    init() {
        let arguments = ProcessInfo.processInfo.arguments
        let server = InvitationsStubServer(scenario: .init(arguments: arguments))
        _model = StateObject(wrappedValue: InvitationsModel(universalLinksEnabled: arguments.contains("--harness-universal"),
                                                            clientFor: { _ in InvitesClient(transport: server) }))
        _signedIn = State(initialValue: !arguments.contains("--harness-signed-out"))
    }

    var body: some View {
        Group {
            if signedIn {
                InvitationGateHost(model: model, signOut: { signedIn = false }) { app }
            } else {
                signIn
            }
        }
        .invitationLinks(model)
        .tint(WelcomePalette.pine)
        .preferredColorScheme(arguments.contains("--harness-dark") ? .dark : .light)
        .onChange(of: signedIn, initial: true) { _, value in
            model.bind(value ? SessionSnapshot(phase: .authenticated, profile: nil, revision: UInt64(Date().timeIntervalSince1970)) : nil)
        }
        .onAppear {
            model.openHousehold = { input in householdInput = input; return true }
            if let index = arguments.firstIndex(of: "--harness-open-url"), index + 1 < arguments.count, let url = URL(string: arguments[index + 1]) {
                model.open(url)
            }
        }
    }

    private var app: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Cuadrao").font(CuadraoTypography.screen).accessibilityIdentifier("harness.app")
                    if householdInput != nil {
                        Text("Household join opened").accessibilityIdentifier("harness.household.opened")
                    }
                    VStack(spacing: 0) { InvitationsProfileRow(model: model) }
                        .padding(.horizontal, 16)
                        .background(Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 20))
                }.padding(24)
            }.background(Color(uiColor: .systemGroupedBackground))
        }
    }

    private var signIn: some View {
        VStack(spacing: 20) {
            InvitationPendingNotice(model: model)
            Spacer()
            Text("Harness sign-in").font(CuadraoTypography.section).accessibilityIdentifier("harness.signedOut")
            Button("Sign in") { signedIn = true }.buttonStyle(.borderedProminent).accessibilityIdentifier("harness.signIn")
            Button("Cancel sign-in") { }.accessibilityIdentifier("harness.cancelSignIn")
            Spacer()
        }
        .background(WelcomePalette.background.ignoresSafeArea())
    }
}
#endif
