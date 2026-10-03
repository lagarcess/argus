#if DEBUG
import SwiftUI

struct ReleaseUpdatesGallery: View {
    var spanish: Bool = true
    @State private var selectedState = "data"
    @State private var permission: ReleasePushPermission = .notDetermined
    @State private var readIDs: Set<String> = []
    @State private var more: ReleaseUpdatesMore = .failure
    @State private var previewPermission = false
    @State private var openedSource = false
    @State private var openedSettings = false
    private let kinds: [ReleaseUpdateKind] = [
        .bill(name: "Electricidad", reminder: .threeDaysBefore),
        .bill(name: "Internet", reminder: .dueToday), .draftReady,
        .invitationAccepted(member: "Alex"), .householdAdminHandoff, .householdClosed,
        .movedAccountHistory(account: "Cuenta del hogar"), .ownerHistoryRemoved,
        .formerMember(plan: "Casa", closedBalance: ReleaseClosedBalance(amount: 1250, currency: "DOP")),
        .formerMember(plan: "Viaje", closedBalance: nil), .reassignResponsibilities(plan: "Casa"), .newPlanOwner(plan: "Casa")
    ]
    private var state: ReleaseUpdatesState {
        switch selectedState {
        case "unavailable": .unavailable
        case "loading": .loading
        case "empty": .empty
        case "error": .failure
        default: .loaded(kinds.enumerated().map { index, kind in
            ReleaseUpdateItem(id: String(index), kind: kind, occurredAt: Date(timeIntervalSince1970: 1_791_000_000),
                              isRead: readIDs.contains(String(index)), source: source(kind))
        }, more: more)
        }
    }
    private func source(_ kind: ReleaseUpdateKind) -> ReleaseUpdateSource {
        switch kind {
        case .bill: .available(.bill("preview"))
        case .draftReady: .available(.document("preview"))
        case .invitationAccepted, .householdAdminHandoff: .available(.household("preview"))
        case .householdClosed, .ownerHistoryRemoved: .unavailable
        case .movedAccountHistory: .available(.account("preview"))
        case .formerMember, .newPlanOwner, .reassignResponsibilities: .available(.plan("preview"))
        }
    }
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Menu(spanish ? "Estado" : "State") {
                    ForEach(["data", "empty", "loading", "error", "unavailable"], id: \.self) { value in
                        Button(stateLabel(value)) { selectedState = value }
                    }
                }.accessibilityIdentifier("updates-gallery-state")
                Spacer()
                Menu(spanish ? "Permiso" : "Permission") {
                    ForEach(ReleasePushPermission.allCases, id: \.self) { value in
                        Button(permissionLabel(value)) { permission = value }
                    }
                }.accessibilityIdentifier("updates-gallery-permission")
                Spacer()
                NavigationLink(spanish ? "Datos" : "Data") { truthSamples }
                    .accessibilityIdentifier("updates-gallery-truth")
            }.font(CuadraoTypography.supporting).padding(.horizontal, 24).frame(minHeight: 44)
            ReleaseUpdatesInbox(state: state, spanish: spanish, permission: permission,
                retry: { selectedState = "data" }, loadMore: { more = .none },
                markRead: { readIDs.insert($0) }, openSource: { _ in openedSource = true },
                requestPermission: { previewPermission = true }, openSettings: { openedSettings = true })
        }
        .confirmationDialog(spanish ? "Permiso de muestra" : "Sample permission", isPresented: $previewPermission, titleVisibility: .visible) {
            Button(spanish ? "Permitir" : "Allow") { permission = .authorized }
            Button(spanish ? "No permitir" : "Don't allow") { permission = .denied }
        }
        .alert(spanish ? "Origen de muestra" : "Sample source", isPresented: $openedSource) {
            Button(spanish ? "Cerrar" : "Close", role: .cancel) {}
        } message: { Text(spanish ? "Esta vista previa no abre registros reales." : "This preview doesn't open real records.") }
        .alert(spanish ? "Ajustes de muestra" : "Sample Settings", isPresented: $openedSettings) {
            Button(spanish ? "Permitir" : "Allow") { permission = .authorized }
            Button(spanish ? "Desactivar" : "Turn off") { permission = .denied }
            Button(spanish ? "Cancelar" : "Cancel", role: .cancel) {}
        }
    }
    private func stateLabel(_ value: String) -> String {
        switch value {
        case "empty": spanish ? "Vacío" : "Empty"
        case "loading": spanish ? "Cargando" : "Loading"
        case "error": spanish ? "Error" : "Error"
        case "unavailable": spanish ? "No disponible" : "Unavailable"
        default: spanish ? "Con novedades" : "With updates"
        }
    }
    private func permissionLabel(_ value: ReleasePushPermission) -> String {
        switch value {
        case .unavailable: spanish ? "No disponible" : "Unavailable"
        case .notDetermined: spanish ? "Sin decidir" : "Not decided"
        case .requesting: spanish ? "Esperando" : "Waiting"
        case .authorized: spanish ? "Permitido" : "Allowed"
        case .denied: spanish ? "Denegado" : "Denied"
        }
    }
    private var truthSamples: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                Text(spanish ? "Mes sin registros" : "Month without records").font(CuadraoTypography.section)
                ReleaseMonthComparison(current: .noRecords, previous: .recorded(100), currency: "DOP", spanish: spanish)
                Divider()
                Text(spanish ? "Comparación con cero registrado" : "Comparison with a recorded zero").font(CuadraoTypography.section)
                ReleaseMonthComparison(current: .recorded(250), previous: .recorded(0), currency: "DOP", spanish: spanish)
                ReleaseMonthComparison(current: .recorded(0), previous: .recorded(0), currency: "DOP", spanish: spanish)
                Divider()
                ReleaseHistoryAccessNote(access: .readOnly, spanish: spanish)
                ReleaseHistoryRecordRow(title: spanish ? "Compra del hogar" : "Household purchase", amount: 400, currency: "DOP",
                    date: Date(timeIntervalSince1970: 1_791_000_000), access: .movedOutOfHousehold, spanish: spanish)
            }.padding(24)
        }.background(WelcomePalette.background).navigationTitle(spanish ? "Datos registrados" : "Recorded data")
    }
}
#endif
