import SwiftUI
import ArgusSession

private extension Locale {
    var spanish: Bool { language.languageCode?.identifier == "es" }
}

/// Shows the beta gate only when the server says this person still needs an invitation.
struct InvitationGateHost<Content: View>: View {
    @ObservedObject var model: InvitationsModel
    var household: HouseholdModel?
    var signOut: (() -> Void)?
    @ViewBuilder let content: () -> Content
    @Environment(\.locale) private var locale
    @Environment(\.openURL) private var openURL
    @Environment(\.scenePhase) private var phase

    var body: some View {
        Group {
            switch model.admission {
            case .checking:
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
                    .accessibilityIdentifier("invites.access.checking")
            case .unanswered:
                unanswered
            case .required(let destinations):
                gate(destinations)
            case .admitted, .off:
                content()
            }
        }
        .task(id: model.identity?.revision) { await model.refreshAccess() }
        .onChange(of: phase) { _, value in if value == .active { Task { await model.refreshAccess() } } }
        .invitationNotices(model)
    }

    private var unanswered: some View {
        VStack(spacing: 16) {
            Text(locale.spanish ? "No pudimos comprobar tu acceso a la beta. Revisa tu conexión e intenta de nuevo."
                 : "We couldn't check your beta access. Check your connection and try again.")
                .font(CuadraoTypography.supporting).multilineTextAlignment(.center)
            Button(locale.spanish ? "Reintentar" : "Try again") { Task { await model.retryAccess() } }
                .buttonStyle(.borderedProminent).frame(minHeight: 44).accessibilityIdentifier("invites.access.retry")
            signOutButton
        }
        .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(WelcomePalette.background.ignoresSafeArea())
        .foregroundStyle(WelcomePalette.ink).tint(WelcomePalette.pine)
        .accessibilityElement(children: .contain).accessibilityIdentifier("invites.access.unanswered")
    }

    @ViewBuilder private var signOutButton: some View {
        if let signOut {
            Button(locale.spanish ? "Cerrar sesión" : "Sign out", action: signOut)
                .frame(minHeight: 44).accessibilityIdentifier("invites.gate.signOut")
        }
    }

    private func gate(_ destinations: InviteDestinations) -> some View {
        ReleaseInviteGate(state: InvitationCopy.gateState(model.gate), code: $model.gateCode, spanish: locale.spanish,
                          onSubmit: { code in Task { await model.submitCode(code) } },
                          onWaitlist: { if let url = destinations.waitlist { openURL(url) } },
                          showsWaitlist: destinations.waitlist != nil)
            .safeAreaInset(edge: .bottom) { signOutButton }
            .background {
                if let household {
                    HouseholdPresenter(model: household)
                    HouseholdAdmissionWatcher(household: household) { Task { await model.refreshAccess() } }
                }
            }
    }
}

/// Accepting a Household invitation also admits the person; the gate re-reads access instead of assuming it.
private struct HouseholdAdmissionWatcher: View {
    @ObservedObject var household: HouseholdModel
    let changed: () -> Void
    var body: some View {
        Color.clear.frame(width: 0, height: 0).onChange(of: household.selectedId) { _, _ in changed() }
    }
}

/// Signed out with a link in hand: the intent waits for sign-in, and cancelling sign-in keeps it.
struct InvitationPendingNotice: View {
    @ObservedObject var model: InvitationsModel
    @Environment(\.locale) private var locale

    var body: some View {
        if model.pendingLink != nil {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Image(systemName: "envelope.open").accessibilityHidden(true)
                Text(locale.spanish ? "Tienes una invitación guardada. Inicia sesión o crea una cuenta para continuar."
                     : "Your invitation is saved. Sign in or create an account to continue.")
                    .font(CuadraoTypography.supporting).fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
                Button(locale.spanish ? "Descartar" : "Discard") { model.discardPendingLink() }
                    .frame(minHeight: 44).accessibilityIdentifier("invites.pending.discard")
            }
            .padding(.horizontal, 20).padding(.vertical, 8)
            .background(WelcomePalette.surface)
            .foregroundStyle(WelcomePalette.ink).tint(WelcomePalette.pine)
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("invites.pending")
        }
    }
}

struct InvitationsProfileRow: View {
    @ObservedObject var model: InvitationsModel
    @Environment(\.locale) private var locale

    var body: some View {
        if model.showsInvitations {
            Divider()
            NavigationLink { InvitationsHub(model: model) } label: {
                HStack(spacing: 12) {
                    Image(systemName: "person.badge.plus").frame(width: 24)
                    Text(locale.spanish ? "Invitaciones" : "Invitations").foregroundStyle(.primary)
                    Spacer()
                    Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary)
                }.frame(minHeight: 58).contentShape(Rectangle())
            }.accessibilityIdentifier("invites.profile")
        }
    }
}

struct InvitationsHub: View {
    @ObservedObject var model: InvitationsModel
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.spanish }

    var body: some View {
        List {
            Section {
                NavigationLink { PersonalInvitationsScreen(model: model) } label: {
                    Label(spanish ? "Invitar a la beta" : "Invite to the beta", systemImage: "person.badge.plus")
                }.accessibilityIdentifier("invites.personal")
            } footer: {
                Text(spanish ? "Las invitaciones al Hogar se envían desde tu Hogar. No usan estas invitaciones."
                     : "Household invitations are sent from your Household. They don't use these invitations.")
            }
            Section(spanish ? "Enviadas" : "Sent") {
                switch model.personal {
                case .loading:
                    ProgressView().accessibilityIdentifier("invites.sent.loading")
                case .failed:
                    Text(spanish ? "No pudimos cargar tus invitaciones. Desliza hacia abajo para intentar de nuevo."
                         : "We couldn't load your invitations. Pull down to try again.")
                        .foregroundStyle(.secondary).accessibilityIdentifier("invites.sent.failed")
                case .ready(let sent):
                    if sent.invitations.isEmpty {
                        Text(spanish ? "Todavía no has enviado invitaciones." : "You haven't sent any invitations yet.")
                            .foregroundStyle(.secondary).accessibilityIdentifier("invites.sent.empty")
                    }
                    ForEach(sent.invitations) { SentInvitationRow(invite: $0) }
                }
            }
            if case .ready(.links(let links)) = model.groupLinks {
                Section(spanish ? "Enlaces de grupo" : "Group links") {
                    ForEach(links) { link in
                        GroupLinkRow(link: link) { Task { await model.revokeGroupLink(link.id) } }
                    }
                    NavigationLink { GroupLinkScreen(model: model) } label: {
                        Label(spanish ? "Nuevo enlace de grupo" : "New group link", systemImage: "link.badge.plus")
                    }.accessibilityIdentifier("invites.group.new")
                }
            }
        }
        .navigationTitle(spanish ? "Invitaciones" : "Invitations")
        .navigationBarTitleDisplayMode(.inline).toolbar(.visible, for: .navigationBar)
        .refreshable { await reload() }
        .task { await reload() }
    }

    private func reload() async {
        await model.loadPersonal()
        await model.loadGroupLinks()
    }
}

private struct SentInvitationRow: View {
    let invite: SentInvite
    @Environment(\.locale) private var locale

    var body: some View {
        let spanish = locale.spanish
        VStack(alignment: .leading, spacing: 4) {
            Text(invite.kind == .household ? (spanish ? "Hogar" : "Household") : (spanish ? "Beta" : "Beta"))
                .font(CuadraoTypography.supporting)
            Text(state(spanish)).font(CuadraoTypography.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("invites.sent." + invite.state.rawValue)
    }

    private func state(_ spanish: Bool) -> String {
        switch invite.state {
        case .accepted:
            let day = invite.acceptedAt?.formatted(date: .abbreviated, time: .omitted) ?? ""
            return spanish ? "Aceptada \(day)" : "Accepted \(day)"
        case .pending:
            let day = invite.expiresAt?.formatted(date: .abbreviated, time: .omitted) ?? ""
            return spanish ? "Sin aceptar · vence \(day)" : "Not accepted yet · expires \(day)"
        case .expired: return spanish ? "Vencida sin aceptar" : "Expired without being accepted"
        case .revoked: return spanish ? "Revocada" : "Revoked"
        }
    }
}

private struct GroupLinkRow: View {
    let link: GroupLink
    let revoke: () -> Void
    @Environment(\.locale) private var locale

    var body: some View {
        let spanish = locale.spanish
        VStack(alignment: .leading, spacing: 4) {
            Text(link.sourceLabel).font(CuadraoTypography.supporting)
            Text(spanish ? "\(link.redeemed) de \(link.cap) lugares usados" : "\(link.redeemed) of \(link.cap) places used")
                .font(CuadraoTypography.caption)
            Text(stateText(spanish)).font(CuadraoTypography.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("invites.group." + link.state.rawValue)
        .swipeActions {
            if link.state == .open {
                Button(spanish ? "Revocar" : "Revoke", role: .destructive, action: revoke)
            }
        }
    }

    private func stateText(_ spanish: Bool) -> String {
        let day = link.expiresAt.formatted(date: .abbreviated, time: .shortened)
        switch link.state {
        case .open: return spanish ? "Abierto · vence \(day)" : "Open · expires \(day)"
        case .full:
            return spanish ? "Lleno. Quien lo abra ahora va a la lista de espera (\(link.overflow) intentos)."
                : "Full. Anyone who opens it now goes to the waitlist (\(link.overflow) attempts)."
        case .expired: return spanish ? "Vencido. Ya no admite a nadie." : "Expired. It no longer admits anyone."
        case .revoked: return spanish ? "Revocado" : "Revoked"
        }
    }
}

private struct PersonalInvitationsScreen: View {
    @ObservedObject var model: InvitationsModel
    @Environment(\.locale) private var locale

    var body: some View {
        ReleasePersonalInvitationsView(state: state, spanish: locale.spanish) {
            Task { await model.createPersonal() }
        }
        .toolbar(.visible, for: .navigationBar)
        .task { await model.loadPersonal() }
    }

    private var state: ReleasePersonalInvitationState {
        if model.creatingPersonal { return .loading }
        switch model.personal {
        case .loading: return .loading
        case .failed: return .unavailable
        case .ready(let sent):
            let share = model.createdPersonal.map { InvitationCopy.share($0, testFlight: model.admission.destinations?.testFlight) }
            return .ready(remaining: sent.quota.remaining, total: sent.quota.limit, invitation: share)
        }
    }
}

private struct GroupLinkScreen: View {
    @ObservedObject var model: InvitationsModel
    @Environment(\.locale) private var locale

    var body: some View {
        ReleaseFounderGroupInvitationView(isFounder: model.groupLinks != .ready(.notFounder), state: state, spanish: locale.spanish) { label, cap, expiry in
            Task { await model.createGroupLink(label: label, cap: cap, expiresAt: expiry) }
        }
        .toolbar(.visible, for: .navigationBar)
        .onAppear { model.startGroupLink() }
    }

    private var state: ReleaseGroupInvitationState {
        switch model.group {
        case .draft: .draft
        case .creating: .creating
        case .created(let invite, let used):
            .ready(cap: invite.cap ?? 0, used: used, invitation: InvitationCopy.share(invite, testFlight: model.admission.destinations?.testFlight))
        }
    }
}

/// Maps the model's answers onto the release screens' states and copy.
enum InvitationCopy {
    static func gateState(_ gate: InvitationGate) -> ReleaseInviteGateState {
        switch gate {
        case .ready: .ready
        case .checking: .checking
        case .problem(let problem): gateState(problem)
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
        default: .unavailable
        }
    }

    static func share(_ invite: CreatedInvite, testFlight: URL?) -> ReleaseInvitationShare {
        ReleaseInvitationShare(url: invite.link, code: invite.code, expiresAt: invite.expiresAt, testFlightURL: testFlight)
    }
}

extension View {
    func invitationNotices(_ model: InvitationsModel) -> some View { modifier(InvitationNoticeAlert(model: model)) }

    /// Universal links arrive as browsing activity; the legacy scheme arrives as an opened URL.
    func invitationLinks(_ model: InvitationsModel?) -> some View {
        onOpenURL { url in Task { await model?.open(url) } }
            .onContinueUserActivity(NSUserActivityTypeBrowsingWeb) { activity in
                if let url = activity.webpageURL { Task { await model?.open(url) } }
            }
    }
}

private struct InvitationNoticeAlert: ViewModifier {
    @ObservedObject var model: InvitationsModel
    @Environment(\.locale) private var locale

    func body(content: Content) -> some View {
        content.alert(title, isPresented: Binding(get: { model.notice != nil }, set: { if !$0 { model.notice = nil } })) {
            Button("OK") { model.notice = nil }.accessibilityIdentifier("invites.notice.ok")
        } message: { Text(message) }
    }

    private var title: String {
        let spanish = locale.spanish
        switch model.notice {
        case .alreadyAdmitted: return spanish ? "Ya tienes acceso" : "You already have access"
        case .secretsShownOnce: return spanish ? "Invitación creada" : "Invitation created"
        default: return spanish ? "Invitación" : "Invitation"
        }
    }

    private var message: String {
        let spanish = locale.spanish
        switch model.notice {
        case .alreadyAdmitted:
            return spanish ? "Tu cuenta ya está en la beta. Esta invitación no se usó." : "Your account is already in the beta. This invitation was not used."
        case .secretsShownOnce:
            return spanish ? "El enlace y el código solo se muestran una vez. Crea otra invitación para compartirla."
                : "The link and code are shown only once. Create another invitation to share it."
        case .householdUnavailable:
            return spanish ? "Las invitaciones al Hogar no están disponibles ahora." : "Household invitations aren't available right now."
        case .groupLink(let invalid):
            switch invalid {
            case .label: return spanish ? "El nombre del enlace debe tener entre 1 y 80 caracteres." : "The link name must be between 1 and 80 characters."
            case .cap: return spanish ? "El límite debe estar entre 1 y 10,000 personas." : "The limit must be between 1 and 10,000 people."
            case .expiry: return spanish ? "El enlace debe vencer en el futuro y dentro de un año." : "The link must expire in the future and within one year."
            }
        case .problem(let problem):
            switch problem {
            case .refused: return spanish ? "No pudimos completar esa solicitud. Revisa los datos e intenta de nuevo." : "We couldn't complete that request. Check the details and try again."
            case .quotaExhausted: return spanish ? "Ya usaste tus invitaciones disponibles." : "You've used your available invitations."
            case .founderOnly: return spanish ? "Solo Lucas puede crear enlaces de grupo." : "Only Lucas can create group links."
            case .invitationRequired: return spanish ? "Necesitas entrar a la beta antes de invitar a otras personas." : "You need beta access before you can invite others."
            case .rateLimited: return ReleaseInviteGateState.rateLimited.message(spanish: spanish) ?? ""
            case .invalid, .expired, .revoked, .used, .full:
                return InvitationCopy.gateState(problem).message(spanish: spanish) ?? ""
            default: return ReleaseInviteGateState.unavailable.message(spanish: spanish) ?? ""
            }
        case nil: return ""
        }
    }
}
