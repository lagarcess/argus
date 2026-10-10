import SwiftUI
import ArgusSession

@MainActor
final class FinancialAssetEditor: ObservableObject, Identifiable {
    enum Phase { case editing, review, saving, uncertain, conflict, saved }
    let id = UUID()
    let account: FinancialAccount
    let selected: FinancialAssetEstimate?
    let details: Bool
    @Published var amount: String
    @Published var basis: String
    @Published var reason = ""
    @Published var date: Date
    @Published var timeZone: String
    @Published var share: String
    @Published var debtID: UUID?
    @Published private(set) var phase = Phase.editing
    @Published private(set) var preview: FinancialAssetPreview?
    @Published private(set) var errorKey: String?
    private let loop: FinancialLoopModel
    private var command: FinancialAssetEstimateCommand?
    private var detailsCommand: FinancialAssetDetailsCommand?
    private let key = UUID()

    init(account: FinancialAccount, correcting: FinancialAssetEstimate?, details: Bool, loop: FinancialLoopModel) {
        self.account = account; selected = correcting; self.details = details; self.loop = loop
        amount = correcting.map { AccountPresentation.amount($0.amount, locale: .current) } ?? ""
        basis = correcting?.estimateBasis ?? ""
        date = correcting.flatMap { AccountPresentation.parseDate($0.asOf) } ?? Date()
        timeZone = correcting?.timeZone ?? "America/Santo_Domingo"
        share = AssetShareControl.percent(account.ownershipShareBps)
        debtID = account.asset?.relatedDebtAccountId
    }

    var locked: Bool { phase != .editing }
    var uncertain: Bool { phase == .uncertain }
    func edit() { guard phase == .review else { return }; phase = .editing; preview = nil; command = nil }

    func save(locale: Locale) async {
        guard phase != .saving, phase != .conflict, phase != .saved else { return }
        errorKey = nil
        let wasReviewed = phase == .review || phase == .uncertain
        phase = .saving
        do {
            if details {
                if detailsCommand == nil {
                    detailsCommand = FinancialAssetDetailsCommand(expectedVersion: account.version,
                        ownershipShareBps: try AccountEntry.share(share), relatedDebtAccountId: debtID)
                }
                _ = try await loop.confirmAccount(detailsCommand!, accountID: account.id, suffix: "/asset-details", method: "PUT", key: key)
            } else if !wasReviewed {
                guard let value = try AccountEntry.amount(amount, locale: locale) else { throw AccountEntry.Failure.amount }
                var proposed = FinancialAssetEstimateCommand(expectedVersion: account.version, amount: value,
                    asOf: ISO8601DateFormatter().string(from: date), timeZone: timeZone,
                    estimateBasis: basis.isEmpty ? nil : basis, reason: selected == nil ? nil : reason,
                    recordId: selected?.recordId, expectedRevision: selected?.revision)
                let response = try await loop.previewAsset(account.id, command: proposed)
                proposed.previewToken = response.previewToken
                command = proposed; preview = response; phase = .review
                return
            } else {
                guard let command else { throw SessionFailure.invalidResponse }
                _ = try await loop.confirmAccount(command, accountID: account.id, suffix: "/asset-estimates", method: "POST", key: key)
            }
            phase = .saved
        } catch {
            errorKey = FinancialActivityEditor.message(error)
            if let failure = error as? AccountEntry.Failure { errorKey = failure == .share ? "accounts.error.share" : "accounts.error.amount_invalid" }
            if case SessionFailure.rejected(_, let code) = error {
                if code == "estimate_date_order" { errorKey = "assets.error.dateOrder" }
                if code == "liability_required" { errorKey = "assets.error.debt" }
            }
            if loop.pendingConfirmation != nil { phase = .uncertain }
            else if case SessionFailure.rejected(409, _) = error { phase = .conflict }
            else { phase = .editing; command = nil; detailsCommand = nil }
        }
    }
}

struct AssetShareControl: View {
    @Binding var share: String
    @State private var choosing = false
    @State private var custom = false
    static func percent(_ bps: Int) -> String { String(bps / 100) + (bps % 100 == 0 ? "" : "." + String(format: "%02d", bps % 100)) }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                if share == "100" || share == "100.00" { Text("assets.share.allSummary") }
                else { Text("assets.share.summary \(share)") }
                Spacer()
                Button("accounts.type.change") { choosing.toggle() }.frame(minHeight: 44).accessibilityIdentifier("assets.share.change")
            }
            if choosing {
                HStack(spacing: 16) {
                    Button("assets.share.all") { share = "100"; custom = false; choosing = false }.accessibilityIdentifier("assets.share.all")
                    Button("assets.share.half") { share = "50"; custom = false; choosing = false }.accessibilityIdentifier("assets.share.half")
                    Button("assets.share.other") { custom = true }.accessibilityIdentifier("assets.share.other")
                }.frame(minHeight: 44)
                if custom {
                    TextField("accounts.share", text: $share).keyboardType(.decimalPad).textFieldStyle(.roundedBorder)
                        .accessibilityIdentifier("assets.share.percent")
                }
            }
        }.font(ArgusStyle.body(13, relativeTo: .subheadline))
    }
}

struct FinancialAssetForm: View {
    @ObservedObject var model: FinancialAssetEditor
    @ObservedObject var accounts: AccountsModel
    @Environment(\.locale) private var locale
    @Environment(\.dismiss) private var dismiss
    @FocusState private var focused: String?
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text(verbatim: model.account.nickname ?? NSLocalizedString("accounts.type." + model.account.type, comment: ""))
                        .font(ArgusStyle.display(23))
                    if model.details {
                        AssetShareControl(share: $model.share).disabled(model.locked)
                        Text("accounts.share.help").font(ArgusStyle.body(12, relativeTo: .caption))
                        Picker("assets.debt", selection: $model.debtID) {
                            Text("assets.debt.none").tag(nil as UUID?)
                            ForEach(accounts.accounts.filter { $0.nature == "liability" }) { account in
                                Text(verbatim: (account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: "")) + " · " + account.currency).tag(Optional(account.id))
                            }
                        }.frame(minHeight: 48).disabled(model.locked).accessibilityIdentifier("assets.debt.picker")
                        Text("assets.debt.help").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                    } else {
                        VStack(alignment: .leading, spacing: 16) {
                            field("assets.whole", text: $model.amount, id: "assets.amount").keyboardType(.decimalPad)
                            Text(verbatim: model.account.currency).foregroundStyle(ArgusStyle.secondary)
                            DatePicker("assets.date", selection: $model.date, in: ...Date(), displayedComponents: [.date, .hourAndMinute])
                                .environment(\.timeZone, TimeZone(identifier: model.timeZone) ?? .gmt).accessibilityIdentifier("assets.date")
                            Picker("accounts.zone", selection: $model.timeZone) {
                                ForEach(TimeZone.knownTimeZoneIdentifiers, id: \.self) { Text(verbatim: $0).tag($0) }
                            }.accessibilityIdentifier("assets.zone")
                            field("assets.basis", text: $model.basis, id: "assets.basis")
                            if model.selected != nil { field("accounts.reason", text: $model.reason, id: "assets.reason") }
                        }.disabled(model.locked)
                        if let preview = model.preview {
                            Text("loop.after").font(ArgusStyle.display(22))
                            AssetPositionView(account: preview.account)
                            if model.phase == .review { Button("loop.edit") { model.edit() }.accessibilityIdentifier("assets.edit") }
                        }
                    }
                    if let error = model.errorKey { Text(LocalizedStringKey(error)).accessibilityIdentifier("assets.error") }
                    if model.phase == .conflict { Text("accounts.review.required") }
                    if model.uncertain { Text("loop.retry.same") }
                    Button {
                        focused = nil
                        Task { await model.save(locale: locale); if model.phase == .saved { dismiss() } }
                    } label: {
                        Text(model.uncertain ? "accounts.retry" : model.details || model.phase == .review ? "accounts.save" : "loop.review")
                            .frame(maxWidth: .infinity)
                    }.buttonStyle(PillButtonStyle()).disabled(model.phase == .saving || model.phase == .conflict)
                        .accessibilityIdentifier("assets.save")
                }.padding(24)
            }.scrollDismissesKeyboard(.interactively).background(ArgusStyle.background)
                .navigationTitle(model.details ? "assets.details" : model.selected == nil ? "assets.update" : "assets.correct")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    CuadraoCancelToolbar(title: "accounts.cancel", disabled: model.phase == .saving, identifier: "assets.cancel") { dismiss() }
                }.interactiveDismissDisabled(model.phase == .saving)
        }
    }
    private func field(_ label: LocalizedStringKey, text: Binding<String>, id: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label).font(ArgusStyle.body(14, relativeTo: .subheadline))
            TextField(label, text: text).focused($focused, equals: id).padding(14)
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line)).accessibilityIdentifier(id)
        }
    }
}
