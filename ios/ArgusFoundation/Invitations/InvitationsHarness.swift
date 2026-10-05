#if DEBUG
import SwiftUI
import ArgusSession

/// Answers `/api/v1/invites` only in shapes the real routes produce (docs/api/openapi.yaml,
/// src/argus/domain/household/invites.py), so UI tests drive the connected screens and
/// `InvitationsModel` without a server. It never grants real access.
actor InvitationsStubServer: InvitesTransport {
    struct Scenario {
        var surfaceOn = true, gateEnabled = true, admitted = false, founder = false, waitlist = true
        var serverLinks = false
        var quotaUsed = 3, accessDown = 0
        init(arguments: [String]) {
            func number(_ flag: String) -> Int? {
                arguments.firstIndex(of: flag).flatMap { $0 + 1 < arguments.count ? Int(arguments[$0 + 1]) : nil }
            }
            serverLinks = arguments.contains("--harness-server-links")
            quotaUsed = number("--harness-quota-used") ?? 3
            accessDown = number("--harness-access-down") ?? 0
            surfaceOn = !arguments.contains("--harness-surface-off")
            gateEnabled = !arguments.contains("--harness-gate-off")
            admitted = arguments.contains("--harness-admitted")
            founder = arguments.contains("--harness-founder")
            waitlist = !arguments.contains("--harness-no-waitlist")
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
            if scenario.accessDown > 0 { scenario.accessDown -= 1; throw SessionFailure.unavailable }
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
                                            "link": scenario.serverLinks ? "https://cuadrao.ai/invite#harness-only-not-a-real-token-000000000000" : NSNull(),
                                            "source_label": NSNull(), "cap": NSNull(), "replayed": false] as [String: Any],
                             "quota": quota()])
        case ("POST", "/preview"):
            if secret.contains("household") || secret.hasPrefix("HOME") {
                return try json(["kind": "household", "available": true, "expires_at": InvitationDates.string(Date().addingTimeInterval(86_400)), "household_name": "Casa"])
            }
            let found = try lookup(secret)
            return try json(["kind": Self.kind(secret), "available": found == nil, "expires_at": InvitationDates.string(Date().addingTimeInterval(86_400)), "household_name": NSNull()])
        case ("POST", "/redeem"):
            if secret.contains("household") || secret.hasPrefix("HOME") {
                throw SessionFailure.rejected(status: 409, code: "household_invitation_requires_accept")
            }
            if let refusal = try lookup(secret) { throw SessionFailure.rejected(status: 409, code: refusal) }
            let outcome = scenario.admitted ? "already_admitted" : "admitted"
            scenario.admitted = true
            return try json(["admitted": true, "outcome": outcome, "kind": Self.kind(secret), "replayed": false])
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
                                            "link": scenario.serverLinks ? "https://cuadrao.ai/invite#harness-only-group-token-0000000000000000" : NSNull(),
                                            "source_label": label, "cap": cap, "replayed": false] as [String: Any],
                             "quota": NSNull()])
        case ("POST", _) where path.hasPrefix("/group-links/") && path.hasSuffix("/revoke"):
            guard scenario.founder else { throw SessionFailure.rejected(status: 403, code: "founder_required") }
            let id = path.dropFirst("/group-links/".count).dropLast("/revoke".count)
            guard let index = links.firstIndex(where: { ($0["id"] as? String)?.lowercased() == id.lowercased() }) else {
                throw SessionFailure.rejected(status: 404, code: "invitation_not_found")
            }
            links[index]["state"] = "revoked"; links[index]["revoked_at"] = InvitationDates.string(Date())
            return Data()
        default:
            throw SessionFailure.rejected(status: 404, code: "not_found")
        }
    }

    /// Finds the invitation a test's code or link names. Returns nil when it can still admit, or the
    /// redeem refusal when it cannot; preview reports that as `available: false`. Unknown secrets,
    /// the lookup limit and a 5xx fail the same way on both routes.
    private func lookup(_ secret: String) throws -> String? {
        let upper = secret.uppercased()
        func names(_ prefix: String) -> Bool { upper.hasPrefix(prefix) || upper.contains(prefix + "-LINK") }
        if names("BETA") { return nil }
        if names("WAIT") { throw SessionFailure.rejected(status: 429, code: "invite_rate_limited") }
        if names("DOWN") { throw SessionFailure.unavailable }
        let refusals = [("EXPD", "invitation_expired"), ("USED", "invitation_consumed"), ("REVK", "invitation_revoked"), ("FULL", "group_link_full")]
        if let refusal = refusals.first(where: { names($0.0) }) { return refusal.1 }
        throw SessionFailure.rejected(status: 404, code: "invitation_not_found")
    }

    /// `FULL` secrets stand for group links, the only kind with a group-only refusal; every other secret is personal.
    private static func kind(_ secret: String) -> String {
        secret.uppercased().hasPrefix("FULL") ? "group_link" : "beta"
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
        _model = StateObject(wrappedValue: InvitationsModel(flags: InvitationFlags(surface: !arguments.contains("--harness-client-off"), links: arguments.contains("--harness-links")),
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
        .overlay(alignment: .bottom) {
            if householdInput != nil {
                Text("Household join opened").padding().background(.thinMaterial, in: Capsule())
                    .accessibilityIdentifier("harness.household.opened")
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
                Task { await model.open(url) }
            }
        }
    }

    private var app: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Cuadrao").font(CuadraoTypography.screen).accessibilityIdentifier("harness.app")
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
