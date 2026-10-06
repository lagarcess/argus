import SwiftUI

struct ConnectedCuadraoSpaces: View {
    @ObservedObject var model: HouseholdModel
    @Binding var destination: AppDestination
    @EnvironmentObject private var auth: ProfileAuthModel
    /// With no household yet, "+" is the only way in, so the space row shows Personal alone.
    private var showsHousehold: Bool { !model.households.isEmpty || model.active || model.pending != nil }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if model.isAvailable {
                CuadraoSpaceSelectorLayout(selection: model.active ? "household" : "personal",
                    addTitle: NSLocalizedString(showsHousehold ? "household.manage" : "household.addSpace", comment: ""), addIdentifier: "household.add",
                    add: { Task { await model.select(nil); if model.isAvailable { model.showManagement = true } } }) {
                    Button { Task { await model.select(nil) } } label: {
                        CuadraoSpaceLabel(title: NSLocalizedString("household.personal", comment: ""), selected: !model.active)
                    }.id("personal").accessibilityIdentifier("household.personal")
                        .accessibilityAddTraits(model.active ? [] : [.isSelected])
                    if showsHousehold {
                        Menu {
                            ForEach(model.households) { item in
                                Button(item.name ?? NSLocalizedString("household.title", comment: "")) {
                                    Task { await model.select(item.id) }
                                }.accessibilityIdentifier("household.select." + item.id.uuidString)
                            }
                            Button("household.manage") { model.showManagement = true }
                        } label: {
                            CuadraoSpaceLabel(title: model.household?.name ?? NSLocalizedString("household.title", comment: ""), selected: model.active)
                        }.id("household").accessibilityIdentifier("household.selector")
                            .accessibilityAddTraits(model.active ? [.isSelected] : [])
                    }
                }.buttonStyle(.plain)
                if model.errorKey == "household.accessEnded" {
                    Text("household.accessEnded").font(.caption).accessibilityIdentifier("household.accessEnded")
                }
                if model.pending != nil {
                    HStack {
                        Text("household.uncertain")
                        Button("accounts.retry") { Task { await model.retry() } }
                            .accessibilityIdentifier("household.pending.retry").frame(minHeight: 44)
                    }.font(.caption)
                }
            } else if model.availability == .unavailable {
                HStack {
                    Text("household.loadError")
                    Button("accounts.retry") { Task { await model.refresh() } }
                        .accessibilityIdentifier("household.availability.retry").frame(minHeight: 44)
                }.font(.caption)
            } else {
                Text("household.personal").font(.subheadline.weight(.semibold)).frame(minHeight: 44)
            }
        }
        .onAppear {
            model.navigateToAccounts = { destination = .accounts }
            model.addAccount = { Task { await model.select(nil); destination = .accounts; auth.accounts?.create() } }
        }
    }
}
