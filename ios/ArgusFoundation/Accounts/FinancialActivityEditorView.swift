import SwiftUI
import ArgusSession

struct FinancialActivityEditorView: View {
    @ObservedObject var model: FinancialActivityEditor
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale
    @FocusState private var focused: Bool

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    if let occurrence = model.planOccurrence {
                        Text(occurrence.title).font(ArgusStyle.display(22))
                        Text("plan.record.disclosure").font(ArgusStyle.body(13, relativeTo: .subheadline)).foregroundStyle(ArgusStyle.secondary)
                    }
                    if model.kind != .transfer {
                        Text(model.origin.nickname ?? NSLocalizedString("accounts.type." + model.origin.type, comment: ""))
                            .font(ArgusStyle.body(14, relativeTo: .subheadline)).foregroundStyle(ArgusStyle.secondary)
                    }
                    if model.options == nil && model.phase == .editing {
                        if model.errorKey == nil { ProgressView("accounts.loading") }
                        else { Button("accounts.retry") { Task { await model.load() } }.frame(minHeight: 44) }
                    } else if model.canEdit {
                        // Never remount entry during .loading/.review — DatePicker jitter
                        // invalidate() wiped coverage answers before confirm could appear.
                        entry
                    }
                    if let preview = model.preview { review(preview) }
                    if let error = model.errorKey {
                        Text(LocalizedStringKey(error)).foregroundStyle(ArgusStyle.secondary)
                            .accessibilityIdentifier("loop.error")
                    }
                    if model.phase == .uncertain {
                        Text("loop.retry.same").font(ArgusStyle.body(13, relativeTo: .caption))
                    }
                    if model.phase == .conflict || model.phase == .retired {
                        Text(model.phase == .retired ? "auth.error.unauthorized" : "loop.conflict.review")
                        Button("action.close") { dismiss() }.buttonStyle(PillButtonStyle())
                    } else if model.canConfirm {
                        Button {
                            focused = false
                            Task {
                                await model.confirm()
                                if model.phase == .saved { dismiss() }
                            }
                        } label: {
                            Text(model.phase == .uncertain ? "accounts.retry" : model.isCorrection ? "loop.activity.saveCorrection" : "loop.activity.confirm")
                                .frame(maxWidth: .infinity)
                        }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("loop.confirm")
                        if model.phase != .uncertain {
                            Button("loop.edit") { model.edit() }.frame(minHeight: 44).accessibilityIdentifier("loop.edit")
                        }
                    } else if model.phase != .conflict && model.phase != .retired {
                        Button {
                            focused = false
                            Task { await model.review(locale: locale) }
                        } label: { Text("loop.review").frame(maxWidth: .infinity) }
                        .buttonStyle(PillButtonStyle()).disabled(!model.readyToReview || model.busy || model.options == nil)
                        .accessibilityIdentifier("loop.review")
                        if model.phase == .review, model.preview?.ready == false {
                            Button("loop.edit") { model.edit() }.frame(minHeight: 44).accessibilityIdentifier("loop.edit")
                        }
                    }
                    if model.busy { ProgressView("accounts.loading") }
                }.padding(24)
            }
            .background(ArgusStyle.background).scrollDismissesKeyboard(.interactively)
            .navigationTitle(model.isCorrection ? "loop.correction.title" : "loop.activity.record")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("accounts.cancel") { dismiss() }.disabled(model.busy || model.phase == .uncertain)
                }
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer(); Button("accounts.keyboard.done") { focused = false }
                }
            }
            .interactiveDismissDisabled(model.busy || model.phase == .uncertain)
            .task { await model.load() }
        }
    }

    private var entry: some View {
        VStack(alignment: .leading, spacing: 20) {
            if !model.isCorrection && model.planOccurrence == nil && model.goal == nil && model.debt == nil && model.returning == nil {
                VStack(alignment: .leading, spacing: 8) {
                    Text("loop.activity.kind")
                    ScrollView(.horizontal) {
                        HStack(spacing: 8) {
                            ForEach(model.availableKinds, id: \.self) { kind in
                                Button(LocalizedStringKey("loop.kind." + kind.rawValue)) { model.setKind(kind) }
                                    .buttonStyle(PillButtonStyle(primary: model.kind == kind))
                                    .accessibilityIdentifier("loop.kind." + kind.rawValue)
                            }
                        }
                    }.scrollIndicators(.hidden)
                }
            } else {
                Label(LocalizedStringKey("loop.kind." + model.kind.rawValue), systemImage: symbol(model.kind))
            }
            if model.kind == .paymentReversal {
                accountPicker("loop.activity.from", value: $model.destinationAccountId,
                              choices: model.destinationChoices, identifier: "loop.destination", showLabel: true)
                accountPicker("loop.activity.to", value: $model.sourceAccountId,
                              choices: model.sourceChoices, identifier: "loop.source", showLabel: true)
            } else if model.kind.isPaired {
                accountPicker("loop.activity.from", value: $model.sourceAccountId,
                              choices: model.sourceChoices, identifier: "loop.source", showLabel: model.kind == .transfer)
                accountPicker(model.kind == .cardPayment ? "loop.activity.card" : "loop.activity.to",
                              value: $model.destinationAccountId, choices: model.destinationChoices,
                              identifier: "loop.destination", showLabel: model.kind == .transfer)
            } else {
                accountPicker(model.kind == .refund ? "loop.activity.refundTo" : "loop.activity.account",
                              value: $model.accountId, choices: model.singleChoices, identifier: "loop.account")
            }
            VStack(alignment: .leading, spacing: 8) {
                Text(LocalizedStringKey("loop.amount." + model.kind.rawValue))
                HStack {
                    TextField("0.00", text: $model.amount).keyboardType(.decimalPad).focused($focused)
                        .monospacedDigit().accessibilityIdentifier("loop.amount")
                    Text(verbatim: model.origin.currency).foregroundStyle(ArgusStyle.secondary)
                }.padding(.horizontal, 14).frame(minHeight: 52)
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line))
            }
            if model.needsLoanSplit {
                splitField("debt.principal", "loop.principal", $model.principal)
                splitField("debt.interest", "loop.interest", $model.interest)
                splitField("debt.fees", "loop.fees", $model.fees)
                Text("debt.split.disclosure").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
            if model.returning != nil { Text("debt.return.disclosure").foregroundStyle(ArgusStyle.secondary) }
            DatePicker("loop.date", selection: $model.date, in: ...Date(), displayedComponents: .date)
                .accessibilityIdentifier("loop.date")
            if model.kind == .income {
                Picker("loop.activity.source", selection: $model.sourceId) {
                    Text("loop.category.none").tag(nil as String?)
                    ForEach(model.options?.sources ?? [], id: \.self) { source in
                        Text(LocalizedStringKey("loop.source." + source)).tag(Optional(source))
                    }
                }.accessibilityIdentifier("loop.sourceType")
            }
            if model.kind == .refund {
                Picker("loop.activity.purchase", selection: $model.purchaseActivityId) {
                    Text("loop.activity.purchaseNone").tag(nil as UUID?)
                    ForEach(model.purchases) { purchase in
                        Text(purchaseLabel(purchase)).tag(Optional(purchase.activityId))
                    }
                }.accessibilityIdentifier("loop.purchase")
                if model.purchaseActivityId != nil {
                    Text("loop.activity.linkedCategory").font(ArgusStyle.body(12, relativeTo: .caption))
                        .foregroundStyle(ArgusStyle.secondary)
                }
            }
            if model.kind == .expense || (model.kind == .refund && model.purchaseActivityId == nil) {
                Picker("loop.category", selection: $model.categoryId) {
                    Text("loop.category.none").tag(nil as String?)
                    ForEach(model.options?.categories ?? [], id: \.self) { category in
                        Text(LocalizedStringKey("loop.category." + category)).tag(Optional(category))
                    }
                }.accessibilityIdentifier("loop.category")
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("loop.note")
                TextField("loop.note.placeholder", text: $model.note, axis: .vertical)
                    .focused($focused).lineLimit(2...4).padding(14)
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line))
                    .accessibilityIdentifier("loop.note")
                Text("\(model.note.unicodeScalars.count)/200").font(ArgusStyle.body(11, relativeTo: .caption))
                    .foregroundStyle(model.note.unicodeScalars.count > 200 ? .red : ArgusStyle.secondary)
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            if model.isCorrection {
                VStack(alignment: .leading, spacing: 8) {
                    Text("accounts.reason")
                    TextField("accounts.reason", text: $model.reason, axis: .vertical).focused($focused)
                        .padding(14).overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line))
                        .accessibilityIdentifier("loop.reason")
                }
            }
        }.disabled(model.busy)
    }

    private func splitField(_ title: LocalizedStringKey, _ id: String, _ text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) { Text(title); TextField("0.00", text: text).keyboardType(.decimalPad).focused($focused).padding(14).overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line)).accessibilityIdentifier(id) }
    }

    private func accountPicker(_ title: LocalizedStringKey, value: Binding<UUID?>,
                               choices: [FinancialAccount], identifier: String, showLabel: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if showLabel { Text(title).accessibilityIdentifier(identifier + ".label") }
            Picker(title, selection: value) {
                Text("loop.activity.chooseAccount").tag(nil as UUID?)
                ForEach(choices) { account in
                    Text(account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: ""))
                        .tag(Optional(account.id))
                }
            }.accessibilityIdentifier(identifier)
                .labelsHidden()
        }
    }

    private func review(_ preview: FinancialActivityPreview) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(preview.ready ? "loop.activity.impact" : "loop.coverage.question")
                .font(ArgusStyle.display(22))
            ForEach(preview.affectedAccounts) { affected in
                VStack(alignment: .leading, spacing: 12) {
                    Text(accountName(affected.accountId)).font(ArgusStyle.body(15))
                    balance("loop.recorded", value: affected.before, currency: affected.currency)
                    if let after = affected.after { balance("loop.after", value: after, currency: affected.currency) }
                    ForEach(affected.observations, id: \.observationId) { observation in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(observation.kind == "opening" || observation.kind == "opening_balance" ? "loop.coverage.opening" : "loop.coverage.check")
                            Text(verbatim: observation.timeZone.map {
                                AccountPresentation.date(observation.asOf, zone: $0, locale: locale)
                            } ?? observation.asOf)
                                .font(ArgusStyle.body(12, relativeTo: .caption))
                            if model.phase != .uncertain {
                                HStack {
                                    Button("loop.coverage.yes") {
                                        Task { await respond(affected.accountId, observation, included: true) }
                                    }
                                        .buttonStyle(PillButtonStyle(primary: observation.included == true))
                                        .accessibilityIdentifier("loop.coverage.yes." + affected.accountId.uuidString + "." + observation.observationId.uuidString)
                                    Button("loop.coverage.no") {
                                        Task { await respond(affected.accountId, observation, included: false) }
                                    }
                                        .buttonStyle(PillButtonStyle(primary: observation.included == false))
                                        .accessibilityIdentifier("loop.coverage.no." + affected.accountId.uuidString + "." + observation.observationId.uuidString)
                                }
                            }
                        }.font(ArgusStyle.body(13, relativeTo: .subheadline))
                    }
                }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line))
            }
            if let result = model.goalPreview, preview.ready {
                Text("goal.afterContribution").font(ArgusStyle.display(21))
                FinancialGoalSummary(progress: result.goal, compact: true)
                ForEach(result.pools.filter { $0.state == "shortfall" && !$0.affectedGoalIds.isEmpty && ($0.accountId == model.sourceAccountId || $0.accountId == model.destinationAccountId) }) { pool in
                    VStack(alignment: .leading, spacing: 8) {
                        Text(accountName(pool.accountId))
                        Text("goal.reason.pool_shortfall").foregroundStyle(ArgusStyle.negative)
                        Text(pool.affectedGoalNames.joined(separator: " · "))
                        Text(PlanPresentation.money(pool.shortfallMinor ?? "0", currency: pool.currency, digits: result.goal.goal.currencyFractionDigits, locale: locale))
                    }
                }
            }
            if let result = model.debtPreview, preview.ready, let pool = result.debt.fundingPool { FinancialDebtFunding(pool: pool, digits: result.debt.debt.currencyFractionDigits) }
            if model.kind == .debtPayment { Text("debt.cost.disclosure").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary) }
            if model.kind == .transfer || model.kind == .cardPayment {
                Text("loop.activity.pairNote").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
            if model.kind == .refund {
                Text("loop.activity.refundNote").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
        }
    }

    private func respond(_ accountId: UUID, _ observation: FinancialObservation, included: Bool) async {
        await model.answerAndReview(
            accountId: accountId,
            observationId: observation.observationId,
            included: included,
            locale: locale
        )
    }
    private func balance(_ label: LocalizedStringKey, value: FinancialBalance, currency: String) -> some View {
        HStack {
            Text(label).foregroundStyle(ArgusStyle.secondary)
            Spacer()
            if let amount = value.amount {
                Text(verbatim: currency + " " + AccountPresentation.amount(amount, locale: locale)).monospacedDigit()
            } else { Text("accounts.unknown") }
        }.font(ArgusStyle.body(13, relativeTo: .subheadline))
    }
    private func accountName(_ id: UUID) -> String {
        guard let account = model.options?.accounts.first(where: { $0.id == id }) else { return model.origin.nickname ?? model.origin.type }
        return account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: "")
    }
    private func purchaseLabel(_ purchase: FinancialActivityDetail) -> String {
        let name = purchase.note ?? purchase.categoryId.map {
            NSLocalizedString("loop.category." + $0, comment: "")
        } ?? NSLocalizedString("loop.kind.expense", comment: "")
        return name + " · " + purchase.currency + " " + AccountPresentation.amount(purchase.amount, locale: locale)
    }
    private func symbol(_ kind: FinancialActivityKind) -> String {
        switch kind {
        case .expense: "arrow.up.right"
        case .income: "arrow.down.left"
        case .transfer: "arrow.left.arrow.right"
        case .cardPayment, .debtPayment: "creditcard"
        case .paymentReversal: "arrow.uturn.backward"
        case .refund: "arrow.uturn.backward"
        }
    }
}
