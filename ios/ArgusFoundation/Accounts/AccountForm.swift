import SwiftUI

struct AccountForm: View {
    @ObservedObject var model: AccountsModel
    @Environment(\.locale) private var locale
    @State private var choosingType = true
    @State private var otherAssets = false
    private let primaryTypes = ["cash", "checking", "savings", "investment", "credit_card", "other_debt"]

    var body: some View {
        NavigationStack {
            ScrollView {
                if let draft = model.draft {
                    VStack(alignment: .leading, spacing: 24) {
                        if draft.mode != .opening {
                            typeControl(draft)
                            field("accounts.currency", text: binding(\.currency), identifier: "accounts.currency")
                                .textInputAutocapitalization(.characters).autocorrectionDisabled()
                            field("accounts.nickname", text: binding(\.nickname), identifier: "accounts.nickname")
                            DisclosureGroup("accounts.ownership") {
                                field("accounts.share", text: binding(\.share), identifier: "accounts.share").keyboardType(.decimalPad)
                                Text("accounts.share.help").font(ArgusStyle.body(12, relativeTo: .caption))
                            }
                        }
                        if draft.mode != .metadata {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(draft.base?.nature == "liability" || ["credit_card", "other_debt"].contains(draft.type)
                                     ? "accounts.amount.owed" : "accounts.amount")
                                Text(verbatim: draft.currency).foregroundStyle(ArgusStyle.secondary)
                                TextField("accounts.amount.placeholder", text: binding(\.amount))
                                    .keyboardType(.decimalPad).textFieldStyle(.roundedBorder).monospacedDigit()
                                    .frame(minHeight: 48).accessibilityIdentifier("accounts.amount")
                                if let exact = try? AccountEntry.amount(draft.amount, locale: locale) {
                                    Text(verbatim: draft.currency + " " + AccountPresentation.amount(exact, locale: locale)).monospacedDigit()
                                }
                                Text(draft.mode == .opening && draft.base?.opening != nil ? "accounts.amount.unchanged" : "accounts.amount.optional")
                                    .font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                                Text("accounts.amount.format").font(ArgusStyle.body(12, relativeTo: .caption))
                            }
                            if draft.mode == .opening {
                            DisclosureGroup("accounts.date.details") {
                                VStack(alignment: .leading, spacing: 20) {
                                    DatePicker("accounts.date", selection: dateBinding, in: ...Date(), displayedComponents: [.date, .hourAndMinute])
                                        .environment(\.timeZone, TimeZone(identifier: draft.timeZone) ?? .gmt)
                                        .accessibilityIdentifier("accounts.date")
                                    Picker("accounts.zone", selection: binding(\.timeZone)) {
                                        ForEach(TimeZone.knownTimeZoneIdentifiers, id: \.self) { zone in Text(verbatim: zone).tag(zone) }
                                    }.frame(minHeight: 48).accessibilityIdentifier("accounts.zone")
                                }.padding(.top, 12).textInputAutocapitalization(.never).autocorrectionDisabled()
                            }
                            }
                            if draft.mode == .opening {
                                field("accounts.reason", text: binding(\.reason), identifier: "accounts.reason")
                            }
                        }
                        if let error = model.errorKey {
                            Text(LocalizedStringKey(error)).fixedSize(horizontal: false, vertical: true)
                                .accessibilityIdentifier("accounts.form.error")
                        }
                        if model.needsReview {
                            Text("accounts.review.required")
                            if let latest = model.latest {
                                AccountSummary(account: latest)
                                Button("accounts.review.latest") { model.editLatest() }
                                    .buttonStyle(PillButtonStyle(primary: false)).accessibilityIdentifier("accounts.review.latest")
                            } else {
                                Text("accounts.review.unavailable")
                            }
                        } else {
                            if model.createIsFrozen { Text("accounts.create.retry").font(ArgusStyle.body(12, relativeTo: .caption)) }
                            Button(model.createIsFrozen ? "accounts.retry" : "accounts.save") { Task { await model.save(locale: locale) } }
                                .buttonStyle(PillButtonStyle()).disabled(model.busy)
                                .accessibilityIdentifier("accounts.save")
                        }
                        if model.busy { ProgressView("accounts.saving") }
                    }.padding(24)
                }
            }
            .scrollDismissesKeyboard(.interactively)
            .background(ArgusStyle.background)
            .navigationTitle(Text("accounts.form.title"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("accounts.cancel") { model.discard() }.disabled(model.busy)
                        .frame(minHeight: 44).accessibilityIdentifier("accounts.cancel")
                }
            }
            .interactiveDismissDisabled()
        }
    }

    @ViewBuilder private func typeControl(_ draft: AccountDraft) -> some View {
        if draft.mode == .create && choosingType {
            VStack(alignment: .leading, spacing: 0) {
                Text("accounts.type").font(ArgusStyle.display(22))
                ForEach(primaryTypes, id: \.self) { type in typeButton(type) }
                DisclosureGroup("accounts.otherAssets", isExpanded: $otherAssets) {
                    ForEach(["property", "vehicle", "other_asset"], id: \.self) { type in typeButton(type) }
                }.padding(.vertical, 12)
            }
        } else {
            Picker("accounts.type", selection: binding(\.type)) {
                ForEach(primaryTypes + ["property", "vehicle", "other_asset"], id: \.self) { type in
                    Text(LocalizedStringKey("accounts.type." + type)).tag(type)
                }
            }.frame(minHeight: 48).accessibilityIdentifier("accounts.type")
        }
    }

    private func typeButton(_ type: String) -> some View {
        Button { model.draft?.type = type; choosingType = false } label: {
            Text(LocalizedStringKey("accounts.type." + type)).frame(maxWidth: .infinity, alignment: .leading).frame(minHeight: 48)
        }.accessibilityIdentifier("accounts.type." + type)
    }

    private var dateBinding: Binding<Date> {
        Binding(get: {
            let parser = ISO8601DateFormatter()
            parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let raw = model.draft?.asOf ?? ""
            let fractional = parser.date(from: raw)
            parser.formatOptions = [.withInternetDateTime]
            return fractional ?? parser.date(from: raw) ?? Date()
        }, set: { date in
            guard !model.busy else { return }
            let formatter = ISO8601DateFormatter()
            formatter.timeZone = TimeZone(identifier: model.draft?.timeZone ?? "") ?? .gmt
            model.draft?.asOf = formatter.string(from: date)
        })
    }

    private func binding(_ path: WritableKeyPath<AccountDraft, String>) -> Binding<String> {
        Binding(get: { model.draft?[keyPath: path] ?? "" }, set: { value in
            guard !model.busy, !model.createIsFrozen else { return }
            model.draft?[keyPath: path] = value
        })
    }
    private func field(_ key: LocalizedStringKey, text: Binding<String>, identifier: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(key)
            TextField(key, text: text).textFieldStyle(.roundedBorder).frame(minHeight: 48)
                .accessibilityIdentifier(identifier)
        }.disabled(model.busy || model.createIsFrozen)
    }
}
