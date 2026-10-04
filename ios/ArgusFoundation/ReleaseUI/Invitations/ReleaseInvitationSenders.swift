import SwiftUI

enum ReleasePersonalInvitationState {
    case loading
    case unavailable
    case ready(remaining: Int, total: Int, invitation: ReleaseInvitationShare?)
}

struct ReleasePersonalInvitationsView: View {
    let state: ReleasePersonalInvitationState
    let spanish: Bool
    let onCreate: () -> Void

    var body: some View {
        ReleaseInvitationPage(title: spanish ? "Cuadrao se comparte." : "Cuadrao is for sharing.",
                              subtitle: spanish ? "Invita a alguien a poner sus finanzas en orden." : "Invite someone to start organizing their money in Cuadrao.") {
            switch state {
            case .loading:
                ProgressView(spanish ? "Cargando invitaciones…" : "Loading invitations…")
                    .accessibilityIdentifier("release.personalInvites.loading")
            case .unavailable:
                Text(spanish ? "Las invitaciones no están disponibles ahora. Intenta de nuevo más tarde."
                     : "Invitations are unavailable right now. Try again later.")
                    .accessibilityIdentifier("release.personalInvites.unavailable")
            case let .ready(remaining, total, invitation):
                VStack(alignment: .leading, spacing: 20) {
                    Text(spanish ? "Te quedan \(remaining) de \(total) invitaciones" : "You have \(remaining) of \(total) invitations left")
                        .font(CuadraoTypography.section)
                        .accessibilityIdentifier("release.personalInvites.remaining")
                    Text(spanish ? "Cada invitación permite que una persona entre a la beta. No la añade a tu Hogar ni comparte tus cuentas."
                         : "Each invitation lets one person into the beta. It does not add them to your Household or share your accounts.")
                        .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                    if let invitation {
                        ReleaseInvitationShareCard(invitation: invitation, spanish: spanish,
                                                   identifier: "release.personalInvites")
                    }
                    Button(action: onCreate) {
                        Text(spanish ? "Crear invitación" : "Create invitation")
                            .frame(maxWidth: .infinity, minHeight: 48)
                    }
                    .buttonStyle(.borderedProminent).disabled(remaining <= 0)
                    .accessibilityIdentifier("release.personalInvites.create")
                    if remaining <= 0 {
                        Text(spanish ? "Ya usaste tus invitaciones disponibles." : "You've used your available invitations.")
                            .font(CuadraoTypography.supporting)
                    }
                }
            }
        }
    }
}

enum ReleaseGroupInvitationState {
    case unavailable
    case draft
    case creating
    case ready(cap: Int, used: Int, invitation: ReleaseInvitationShare)
}

struct ReleaseFounderGroupInvitationView: View {
    let isFounder: Bool
    let state: ReleaseGroupInvitationState
    let spanish: Bool
    let onCreate: (String, Int, Date) -> Void
    @State private var label = ""
    @State private var cap = ""
    @State private var expiry = Date().addingTimeInterval(7 * 86_400)

    var body: some View {
        ReleaseInvitationPage(title: spanish ? "Una invitación,\nvarios lugares." : "One invitation,\nseveral places.",
                              subtitle: spanish ? "Enlace de grupo para entrar a la beta." : "A group link for beta access.") {
            if !isFounder {
                Text(spanish ? "Solo Lucas puede crear enlaces de grupo." : "Only Lucas can create group links.")
                    .accessibilityIdentifier("release.groupInvite.founderOnly")
            } else {
                VStack(alignment: .leading, spacing: 20) {
                    Text(spanish ? "No usa tus invitaciones personales. No añade personas a un Hogar ni comparte cuentas."
                         : "This does not use your personal invitations. It does not add people to a Household or share accounts.")
                        .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                    switch state {
                    case .unavailable:
                        Text(spanish ? "Los enlaces de grupo no están disponibles ahora." : "Group links are unavailable right now.")
                            .accessibilityIdentifier("release.groupInvite.unavailable")
                    case .draft, .creating:
                        groupForm
                    case let .ready(cap, used, invitation):
                        Text(spanish ? "\(used) de \(cap) lugares usados" : "\(used) of \(cap) places used")
                            .font(CuadraoTypography.section)
                            .accessibilityIdentifier("release.groupInvite.usage")
                        ReleaseInvitationShareCard(invitation: invitation, spanish: spanish,
                                                   identifier: "release.groupInvite")
                        Text(spanish ? "Al llenarse o vencer, el enlace lleva a la lista de espera en cuadrao.ai."
                             : "When full or expired, the link leads to the waitlist at cuadrao.ai.")
                            .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private var creating: Bool {
        if case .creating = state { return true }; return false
    }

    private var groupForm: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(spanish ? "Nombre del enlace" : "Link name").font(CuadraoTypography.supporting)
            TextField(spanish ? "Por ejemplo, cena de lanzamiento" : "For example, launch dinner", text: $label)
                .padding(16)
                .background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 16))
                .accessibilityIdentifier("release.groupInvite.label")
            Text(spanish ? "Límite de personas" : "Number of places").font(CuadraoTypography.supporting)
            TextField(spanish ? "Elige un límite" : "Choose a limit", text: $cap)
                .keyboardType(.numberPad).padding(16)
                .background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 16))
                .accessibilityIdentifier("release.groupInvite.cap")
            DatePicker(spanish ? "Vence" : "Expires", selection: $expiry, in: Date()...,
                       displayedComponents: [.date, .hourAndMinute])
                .accessibilityIdentifier("release.groupInvite.expiry")
            Button {
                let name = label.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !name.isEmpty, let value = Int(cap), value > 0, expiry > Date(), !creating else { return }
                onCreate(name, value, expiry)
            } label: {
                HStack {
                    if creating { ProgressView() }
                    Text(creating ? (spanish ? "Creando…" : "Creating…") : (spanish ? "Crear enlace de grupo" : "Create group link"))
                }.frame(maxWidth: .infinity, minHeight: 48)
            }
            .buttonStyle(.borderedProminent)
            .disabled(label.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || (Int(cap) ?? 0) <= 0 || expiry <= Date() || creating)
            .accessibilityIdentifier("release.groupInvite.create")
        }.disabled(creating)
    }
}
