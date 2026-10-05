import SwiftUI

struct ConnectedCuadraoSpaces: View {
    @ObservedObject var model: HouseholdModel
    @Binding var destination: AppDestination
    @EnvironmentObject private var auth: ProfileAuthModel
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if model.isAvailable {
                HStack(spacing: 4) {
                    HStack(spacing: 24) {
                        Button("household.personal") { Task { await model.select(nil) } }
                            .font(.subheadline.weight(model.active ? .regular : .semibold))
                            .foregroundStyle(model.active ? Color.secondary : Color.primary)
                            .frame(minHeight: 44).accessibilityIdentifier("household.personal")
                        Menu {
                            ForEach(model.households) { item in
                                Button(item.name ?? NSLocalizedString("household.title", comment: "")) {
                                    Task { await model.select(item.id) }
                                }.accessibilityIdentifier("household.select." + item.id.uuidString)
                            }
                            Button("household.manage") { model.showManagement = true }
                        } label: {
                            Text("household.title").font(.subheadline.weight(model.active ? .semibold : .regular))
                                .foregroundStyle(model.active ? Color.primary : Color.secondary).frame(minHeight: 44)
                        }.accessibilityIdentifier("household.selector")
                    }
                    Spacer(minLength: 8)
                    CuadraoSectionAddButton(title: NSLocalizedString("household.manage", comment: "")) {
                        Task { await model.select(nil); if model.isAvailable { model.showManagement = true } }
                    }.accessibilityIdentifier("household.add")
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
