#if DEBUG
import SwiftUI
import ArgusSession

struct ReleaseInvitationsGallery: View {
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        List {
            Section {
                Text(spanish ? "Galería de estados. Los ejemplos no dan acceso ni crean invitaciones."
                     : "State gallery. Examples do not grant access or create invitations.")
            }
            Section(spanish ? "Entrada a la beta" : "Beta entry") {
                ForEach(ReleaseInviteGateState.allCases, id: \.rawValue) { state in
                    NavigationLink(state.title(spanish: spanish)) {
                        ReleaseInviteGateFixture(initialState: state, spanish: spanish)
                    }.accessibilityIdentifier("release.invites.gallery.gate." + state.rawValue)
                }
            }
            Section(spanish ? "Invitaciones personales" : "Personal invitations") {
                NavigationLink(spanish ? "7 de 10 · Enlace, código y QR" : "7 of 10 · Link, code and QR") {
                    ReleasePersonalInvitationFixture(spanish: spanish)
                }.accessibilityIdentifier("release.invites.gallery.personal")
                NavigationLink(spanish ? "Sin invitaciones disponibles" : "No invitations left") {
                    ReleasePersonalInvitationFixture(spanish: spanish, initialRemaining: 0)
                }
                NavigationLink(spanish ? "No disponible" : "Unavailable") {
                    ReleasePersonalInvitationFixture(spanish: spanish, unavailable: true)
                }
            }
            Section(spanish ? "Hogar · Solo administradores" : "Household · Admins only") {
                NavigationLink(spanish ? "Invitación actual de Hogar" : "Current Household invitation") {
                    Form {
                        Text(spanish ? "Ejemplo. Este enlace no permite unirse a un Hogar."
                             : "Example. This link cannot join a Household.")
                        if let invitation = householdFixture {
                            HouseholdInvitationShareView(invitation: invitation, spanish: spanish)
                        }
                    }
                }.accessibilityIdentifier("release.invites.gallery.household")
            }
            Section(spanish ? "Enlace de grupo · Solo Lucas" : "Group link · Lucas only") {
                NavigationLink(spanish ? "Crear con límite y vencimiento" : "Create with cap and expiry") {
                    ReleaseGroupInvitationFixture(spanish: spanish)
                }.accessibilityIdentifier("release.invites.gallery.group.create")
                NavigationLink(spanish ? "Enlace preparado" : "Prepared link") {
                    ReleaseGroupInvitationFixture(spanish: spanish, prepared: true)
                }.accessibilityIdentifier("release.invites.gallery.group.ready")
                NavigationLink(spanish ? "Cuenta sin permiso" : "Account without permission") {
                    ReleaseGroupInvitationFixture(spanish: spanish, isFounder: false)
                }
            }
        }
        .navigationTitle(spanish ? "Invitaciones · Galería" : "Invitations · Gallery")
    }

    private var householdFixture: HouseholdInvitation? {
        let json = """
        {"id":"00000000-0000-0000-0000-000000000001","expires_at":"2026-10-08T00:00:00Z","state":"pending","token":"DEBUG-NOT-A-VALID-INVITATION"}
        """
        return try? JSONDecoder().decode(HouseholdInvitation.self, from: Data(json.utf8))
    }

}

private enum ReleaseInvitationFixtures {
    static func share(expiry: Date = Date(timeIntervalSince1970: 1791417600)) -> ReleaseInvitationShare {
        ReleaseInvitationShare(url: URL(string: "https://cuadrao.ai/invite#DEBUG-NOT-A-VALID-INVITATION")!,
                               code: "DEMO-ONLY", expiresAt: expiry)
    }
}

private struct ReleaseInvitationFixtureNotice: View {
    let spanish: Bool
    var body: some View {
        Text(spanish ? "Ejemplo local. El menú Resultado completa la solicitud. No cambia tu acceso ni tu Hogar."
             : "Local fixture. Use Result to complete the request. Your access and Household do not change.")
            .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            .padding(12).frame(maxWidth: .infinity)
            .background(WelcomePalette.surface)
            .accessibilityIdentifier("release.invites.fixture.notice")
    }
}

private struct ReleaseInviteGateFixture: View {
    let spanish: Bool
    @Environment(\.openURL) private var openURL
    @State private var state: ReleaseInviteGateState
    @State private var code = ""
    @State private var accepted = false

    init(initialState: ReleaseInviteGateState, spanish: Bool) {
        self.spanish = spanish
        _state = State(initialValue: initialState)
    }

    var body: some View {
        Group {
            if accepted {
                ReleaseInvitationPage(title: spanish ? "Invitación aceptada." : "Invitation accepted.",
                                      subtitle: spanish ? "Este resultado es un ejemplo local. No se cambió tu acceso a Cuadrao."
                                      : "This result is a local fixture. Your Cuadrao access has not changed.") {
                    NavigationLink(spanish ? "Explorar invitaciones personales" : "Explore personal invitations") {
                        ReleasePersonalInvitationFixture(spanish: spanish)
                    }.buttonStyle(.borderedProminent)
                        .accessibilityIdentifier("release.invites.fixture.accepted.continue")
                    Button(spanish ? "Probar otro resultado" : "Try another result") {
                        accepted = false; state = .ready
                    }.frame(minHeight: 44)
                }.accessibilityIdentifier("release.invites.fixture.accepted")
            } else {
                ReleaseInviteGate(state: state, code: $code, spanish: spanish,
                                  onSubmit: { _ in state = .checking },
                                  onWaitlist: { openURL(URL(string: "https://cuadrao.ai")!) })
            }
        }
        .safeAreaInset(edge: .top) { ReleaseInvitationFixtureNotice(spanish: spanish) }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu(spanish ? "Resultado" : "Result") {
                    Button(spanish ? "Aceptada" : "Accepted") { accepted = true }
                        .accessibilityIdentifier("release.invites.fixture.result.accepted")
                    ForEach([ReleaseInviteGateState.invalid, .expired, .full, .consumed, .revoked, .unavailable], id: \.rawValue) { outcome in
                        Button(outcome.title(spanish: spanish)) { state = outcome }
                            .accessibilityIdentifier("release.invites.fixture.result." + outcome.rawValue)
                    }
                }.disabled(state != .checking || accepted)
                    .accessibilityIdentifier("release.invites.fixture.result")
            }
        }
    }
}

private struct ReleasePersonalInvitationFixture: View {
    let spanish: Bool
    @State private var remaining: Int
    @State private var state: ReleasePersonalInvitationState
    @State private var pending = false
    @State private var invitation: ReleaseInvitationShare?

    init(spanish: Bool, initialRemaining: Int = 7, unavailable: Bool = false) {
        self.spanish = spanish
        let share = initialRemaining > 0 ? ReleaseInvitationFixtures.share() : nil
        _remaining = State(initialValue: initialRemaining)
        _invitation = State(initialValue: share)
        _state = State(initialValue: unavailable ? .unavailable : .ready(remaining: initialRemaining, total: 10, invitation: share))
    }

    var body: some View {
        ReleasePersonalInvitationsView(state: state, spanish: spanish) {
            pending = true
            state = .loading
        }
        .safeAreaInset(edge: .top) { ReleaseInvitationFixtureNotice(spanish: spanish) }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu(spanish ? "Resultado" : "Result") {
                    Button(spanish ? "Invitación creada" : "Invitation created") {
                        guard pending, remaining > 0 else { return }
                        remaining -= 1
                        invitation = ReleaseInvitationFixtures.share()
                        pending = false
                        showReady()
                    }.disabled(!pending)
                        .accessibilityIdentifier("release.invites.fixture.personal.complete")
                    Button(spanish ? "No disponible" : "Unavailable") {
                        pending = false; state = .unavailable
                    }.disabled(!pending)
                    Button(spanish ? "Volver a intentar" : "Try again") {
                        pending = false; showReady()
                    }.accessibilityIdentifier("release.invites.fixture.personal.retry")
                }.accessibilityIdentifier("release.invites.fixture.result")
            }
        }
    }

    private func showReady() {
        state = .ready(remaining: remaining, total: 10, invitation: invitation)
    }
}

private struct ReleaseGroupInvitationFixture: View {
    let spanish: Bool
    let isFounder: Bool
    @State private var state: ReleaseGroupInvitationState
    @State private var pending: (cap: Int, expiry: Date)?

    init(spanish: Bool, isFounder: Bool = true, prepared: Bool = false) {
        self.spanish = spanish
        self.isFounder = isFounder
        _state = State(initialValue: prepared ? .ready(cap: 25, used: 8, invitation: ReleaseInvitationFixtures.share()) : .draft)
    }

    var body: some View {
        ReleaseFounderGroupInvitationView(isFounder: isFounder, state: state, spanish: spanish) { _, cap, expiry in
            pending = (cap, expiry)
            state = .creating
        }
        .safeAreaInset(edge: .top) { ReleaseInvitationFixtureNotice(spanish: spanish) }
        .toolbar {
            if isFounder {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu(spanish ? "Resultado" : "Result") {
                        Button(spanish ? "Enlace creado" : "Link created") {
                            guard let values = pending else { return }
                            state = .ready(cap: values.cap, used: 0,
                                           invitation: ReleaseInvitationFixtures.share(expiry: values.expiry))
                            pending = nil
                        }.disabled(pending == nil)
                            .accessibilityIdentifier("release.invites.fixture.group.complete")
                        Button(spanish ? "No disponible" : "Unavailable") {
                            pending = nil; state = .unavailable
                        }.disabled(pending == nil)
                        Button(spanish ? "Editar otro enlace" : "Edit another link") {
                            pending = nil; state = .draft
                        }.accessibilityIdentifier("release.invites.fixture.group.edit")
                    }.accessibilityIdentifier("release.invites.fixture.result")
                }
            }
        }
    }
}
#endif
