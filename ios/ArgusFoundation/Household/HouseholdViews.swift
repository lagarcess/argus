import SwiftUI
import ArgusSession

struct HouseholdControls: View {
    @ObservedObject var model: HouseholdModel
    @Binding var destination: AppDestination
    @EnvironmentObject private var auth: ProfileAuthModel
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if model.isAvailable {
                HStack(spacing: 22) {
                    Button("household.personal") { Task { await model.select(nil) } }
                        .fontWeight(model.active ? .regular : .semibold).foregroundStyle(model.active ? Color.secondary : WelcomePalette.pine)
                        .accessibilityIdentifier("household.personal").frame(minHeight: 44)
                    Menu {
                        ForEach(model.households) { item in
                            Button(item.name ?? NSLocalizedString("household.title", comment: "")) { Task { await model.select(item.id) } }.accessibilityIdentifier("household.select." + item.id.uuidString)
                        }
                        Button("household.manage") { model.showManagement = true }
                    } label: { Text("household.title").fontWeight(model.active ? .semibold : .regular).foregroundStyle(model.active ? WelcomePalette.pine : Color.secondary).frame(minHeight: 44) }
                    .accessibilityIdentifier("household.selector")
                    Button { Task { await model.select(nil); if model.isAvailable { model.showManagement = true } } } label: { Image(systemName: "plus").frame(width: 44, height: 44) }
                        .accessibilityLabel("household.manage").accessibilityIdentifier("household.add")
                    Spacer(minLength: 0)
                }
                if model.errorKey == "household.accessEnded" { Text("household.accessEnded").font(.system(size: 13)).accessibilityIdentifier("household.accessEnded") }
                if model.pending != nil {
                    HStack {
                        Text("household.uncertain").font(.system(size: 13))
                        Button("accounts.retry") { Task { await model.retry() } }.accessibilityIdentifier("household.pending.retry").frame(minHeight: 44)
                    }
                }
            } else if model.availability == .unavailable {
                HStack {
                    Text("household.loadError").font(.system(size: 13))
                    Button("accounts.retry") { Task { await model.refresh() } }
                        .accessibilityIdentifier("household.availability.retry").frame(minHeight: 44)
                }
            }
        }
        .padding(.horizontal, 24)
        .environment(\.colorScheme, .light)
        .onAppear {
            model.navigateToAccounts = { destination = .accounts }
            model.addAccount = { Task { await model.select(nil); destination = .accounts; auth.accounts?.create() } }
        }

    }
}

struct HouseholdDestinationRouter<Personal: View>: View {
    @ObservedObject var model: HouseholdModel
    let tab: AppDestination
    let active: Bool
    @Binding var destination: AppDestination
    @ViewBuilder let personal: () -> Personal
    var body: some View {
        if model.active { HouseholdConnectedDestination(model: model, tab: tab, active: active, destination: $destination) }
        else { personal() }
    }
}

struct HouseholdDestination: View {
    @ObservedObject var model: HouseholdModel
    let tab: AppDestination
    let active: Bool
    @State private var query = ""
    var body: some View {
        if active {
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                if let error = model.errorKey {
                    Text(LocalizedStringKey(error)).accessibilityIdentifier("household.error")
                    Button("accounts.retry") { Task { await model.refresh() } }.frame(minHeight: 44)
                }
                if let detail = model.detail, tab != .plan && tab != .argus {
                    accountDetail(detail)
                } else if tab == .plan || tab == .argus {
                    Text("household.unsupported").foregroundStyle(Color.secondary)
                } else if let snapshot = model.snapshot {
                    HStack {
                        Text(model.household?.name ?? "").font(.system(size: 25, weight: .regular, design: .serif))
                        Spacer()
                        Button("household.people") { model.showManagement = true }.accessibilityIdentifier("household.people").frame(minHeight: 44)
                    }
                    if tab == .home {
                        Text("household.scopeNotice").font(.system(size: 13)).foregroundStyle(Color.secondary)
                        ForEach(snapshot.positions) { position in
                            VStack(alignment: .leading, spacing: 4) {
                                let amount = HouseholdMoney.minor(position.amountMinor, currency: position.currency, digits: position.currencyFractionDigits)
                                Text(position.unknownCount > 0 ? position.currency + " " + NSLocalizedString("household.unknown", comment: "") : amount)
                                    .font(.system(size: 28, weight: .regular, design: .serif)).accessibilityIdentifier("household.position." + position.currency)
                                if position.unknownCount > 0 {
                                    (Text("household.knownSubtotal") + Text(": " + amount))
                                        .font(.system(size: 15)).accessibilityIdentifier("household.position.knownSubtotal." + position.currency)
                                    Text("household.unknownIncluded").font(.system(size: 13)).foregroundStyle(Color.secondary)
                                }
                            }
                        }
                    }
                    if tab == .search { searchContent }
                    else {
                        if snapshot.accounts.isEmpty {
                            Text("household.empty").font(.system(size: 23, weight: .regular, design: .serif))
                            Text("household.consent").foregroundStyle(Color.secondary)
                            Button("household.addAccount") { model.addAccount?() }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("household.addAccount")
                            Text("household.addAccountNotice").font(.system(size: 13)).foregroundStyle(Color.secondary)
                            Button("household.shareAccounts") { model.showManagement = true }.frame(minHeight: 44).accessibilityIdentifier("household.shareAccounts")
                        } else {
                            ForEach(snapshot.accounts) { item in accountRow(item) }
                            Text("household.activity").font(.system(size: 21, weight: .regular, design: .serif))
                            ForEach(snapshot.activities.prefix(tab == .home ? 5 : 30)) { item in activityRow(item) }
                        }
                    }
                } else if model.errorKey == nil { ProgressView("accounts.loading") }
            }.padding(24)
        }.accessibilityIdentifier("screen." + tab.rawValue)
        .refreshable { await model.foreground() }
        .onChange(of: model.highlightActivityId) { _, id in if let id { proxy.scrollTo(id, anchor: .top) } }
        }
        } else { Color.clear }
    }
    private var searchContent: some View {
        VStack(alignment: .leading, spacing: 16) {
            TextField("household.search", text: $query).textFieldStyle(.roundedBorder).submitLabel(.search)
                .accessibilityIdentifier("household.search.query").onSubmit { Task { await model.find(query) } }
            if model.searchState == .loading { ProgressView("accounts.loading") }
            if model.searchState == .empty { Text("household.searchEmpty").foregroundStyle(Color.secondary).accessibilityIdentifier("household.search.empty") }
            if model.searchState == .unavailable { Text("household.loadError"); Button("accounts.retry") { Task { await model.find(query) } }.frame(minHeight: 44) }
            ForEach(model.search) { item in
                Button { Task { await model.openSearchHit(item) } } label: {
                    HStack { Text(item.title); Spacer(); Image(systemName: "chevron.right") }.frame(minHeight: 44)
                }.accessibilityIdentifier("household.search." + item.id.uuidString)
            }
            if model.nextCursor != nil { Button("household.more") { Task { await model.find(query, more: true) } }.frame(minHeight: 44) }
        }
    }
    private func accountRow(_ item: HouseholdAccount) -> some View {
        Button { Task { await model.open(item.id) } } label: {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(item.account.nickname ?? NSLocalizedString("accounts.type." + item.account.type, comment: ""))
                    Spacer()
                    Text(item.account.balance.amount.map { item.account.currency + " " + $0 } ?? NSLocalizedString("household.unknown", comment: "")).monospacedDigit()
                }
                Text(item.ownerName + " · " + NSLocalizedString("household.permission." + item.permission, comment: "")).font(.system(size: 12)).foregroundStyle(Color.secondary)
            }.frame(minHeight: 54).contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityIdentifier("household.account." + item.id.uuidString)
    }
    @ViewBuilder private func accountDetail(_ detail: HouseholdAccountDetail) -> some View {
        Button("accounts.back") { model.back() }.accessibilityIdentifier("household.back").frame(minHeight: 44)
        Text(detail.account.account.nickname ?? "").font(.system(size: 26, weight: .regular, design: .serif))
        Text(detail.account.account.balance.amount.map { detail.account.account.currency + " " + $0 } ?? NSLocalizedString("household.unknown", comment: "")).font(.system(size: 30, weight: .regular, design: .serif)).accessibilityIdentifier("household.detail.balance")
        Text(detail.account.ownerName + " · " + NSLocalizedString("household.permission." + detail.account.permission, comment: ""))
        if detail.account.account.ownershipShareBps != 10000 {
            Text("household.wholeValue").foregroundStyle(Color.secondary)
            Text(Decimal(detail.account.account.ownershipShareBps) / 100, format: .number).bold() + Text("%")
        }
        if detail.account.permission == "edit" && !detail.account.account.isOptionalAsset {
            Button("household.recordActivity") { model.beginActivity(detail.account) }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("household.record")
        }
        ForEach(detail.activities) { item in
            if model.highlightActivityId == item.id { Text("household.selectedActivity").font(.system(size: 13)).foregroundStyle(Color.secondary) }
            activityRow(item).id(item.id)
            HStack {
                Button("household.history") { Task { await model.loadHistory(item.id) } }.frame(minHeight: 44).accessibilityIdentifier("household.history." + item.id.uuidString)
                if item.canEdit { Button("household.correct") { model.beginActivity(detail.account, correction: item) }.frame(minHeight: 44).accessibilityIdentifier("household.correct." + item.id.uuidString) }
            }
        }
        ForEach(Array(model.history.enumerated()), id: \.offset) { _, item in activityRow(item) }
    }
    private func activityRow(_ item: HouseholdActivity) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(item.activity.note ?? NSLocalizedString("loop.kind." + item.activity.kind.rawValue, comment: ""))
                Spacer()
                if let amount = item.activity.amount { Text(item.activity.currency + " " + amount).monospacedDigit() }
                else if let leg = item.activity.legs.first { Text(HouseholdMoney.minor(leg.balanceMovementMinor, currency: item.activity.currency, digits: item.activity.currencyFractionDigits)).monospacedDigit() }
            }
            if item.privateCounterpart { Text("household.privateCounterpart").font(.system(size: 12)).foregroundStyle(Color.secondary) }
            Text(item.authorName.isEmpty ? NSLocalizedString("household.formerMember", comment: "") : item.authorName).font(.system(size: 12)).foregroundStyle(Color.secondary)
        }.frame(minHeight: 50).accessibilityIdentifier("household.activity." + item.id.uuidString)
    }
}

enum HouseholdMoney {
    static func minor(_ amount: Int64, currency: String, digits: Int) -> String {
        currency + " " + AccountPresentation.amount(AccountPresentation.decimal(amount, digits: digits), locale: .current)
    }
}

struct HouseholdConnectedDestination: View {
    @ObservedObject var model: HouseholdModel
    let tab: AppDestination
    let active: Bool
    @Binding var destination: AppDestination
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if active {
                CuadraoBrand().padding(.horizontal, 24).padding(.top, 28)
                HouseholdControls(model: model, destination: $destination)
            }
            HouseholdDestination(model: model, tab: tab, active: active)
        }.background(Color.white).tint(WelcomePalette.pine)
        .environment(\.colorScheme, .light)
    }
}

struct HouseholdPresenter: View {
    @ObservedObject var model: HouseholdModel
    @EnvironmentObject private var auth: ProfileAuthModel
    @Environment(\.scenePhase) private var phase
    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .task(id: model.identity?.revision) { await model.refresh() }
            .onChange(of: phase) { _, phase in if phase == .active { Task { await model.foreground() } } }
            .sheet(isPresented: Binding(get: { model.isAvailable && model.showManagement }, set: { model.showManagement = $0 })) { HouseholdManagement(model: model, accounts: auth.accounts).tint(ArgusStyle.ink).foregroundStyle(ArgusStyle.ink) }
            .sheet(item: Binding(get: { model.isAvailable ? model.editor : nil }, set: { model.editor = $0 })) { HouseholdActivityEditorView(model: $0).tint(ArgusStyle.ink).foregroundStyle(ArgusStyle.ink) }
    }
}
