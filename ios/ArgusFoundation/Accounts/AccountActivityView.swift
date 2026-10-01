import SwiftUI
import ArgusSession

struct AccountActivityView: View {
    @ObservedObject var loop: FinancialLoopModel
    let account: FinancialAccount
    @State private var pendingCorrection: FinancialActivityDetail?
    @State private var pendingReturn: FinancialActivityDetail?
    @State private var inspected: FinancialActivity?
    @Environment(\.locale) private var locale

    private var page: FinancialLoopModel.AccountReadState { loop.read(account.id) }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Button { loop.record(account) } label: {
                Label("loop.record", systemImage: "plus").frame(maxWidth: .infinity)
            }.buttonStyle(PillButtonStyle()).disabled(loop.pendingConfirmation != nil).accessibilityIdentifier("accounts.record")
            if ["credit_card", "other_debt"].contains(account.type) {
                if let progress = loop.plan.projection?.debts?.first(where: { !$0.debt.archived && $0.debt.debtAccountId == account.id }) {
                    Button("debt.view") { Task { await loop.debts.open(progress.id, origin: .account) } }.frame(minHeight: 44).accessibilityIdentifier("accounts.debt")
                } else { Button("debt.add") { loop.debts.create(account) }.frame(minHeight: 44).accessibilityIdentifier("accounts.debt") }
            }
            Button("loop.check.title") { loop.check(account) }.frame(minHeight: 44)
                .accessibilityIdentifier("accounts.check")
            if let error = page.errorKey {
                Text(LocalizedStringKey(error)).foregroundStyle(ArgusStyle.secondary)
                Button("accounts.retry") { Task { await loop.open(account) } }
            }
            if !page.activity.isEmpty {
                Text("loop.recent").font(ArgusStyle.display(22))
                VStack(spacing: 0) {
                    ForEach(page.activity, id: \.recordId) { activity in
                        Button { inspected = activity } label: {
                            FinancialActivityRow(activity: activity, currency: account.currency)
                        }.buttonStyle(.plain).accessibilityIdentifier("activity.row." + activity.recordId.uuidString)
                    }
                }
            }
            if page.activityCursor != nil { Button("loop.more") { Task { await loop.more(account, checks: false) } }.disabled(page.loadingMore) }
            if !page.checks.isEmpty {
                Text("loop.check.history").font(ArgusStyle.display(22))
                ForEach(page.checks, id: \.recordId) { check in
                    VStack(alignment: .leading, spacing: 8) {
                        Label(check.kind == "value_update" ? "loop.check.value" : "loop.check.title", systemImage: "checkmark.circle")
                        Text(verbatim: account.currency + " " + AccountPresentation.amount(AccountPresentation.decimal(check.observedAmountMinor, digits: account.currencyFractionDigits), locale: locale))
                            .monospacedDigit()
                        Text(verbatim: AccountPresentation.date(check.asOf, zone: check.timeZone, locale: locale))
                            .font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                        if let difference = check.differenceMinor {
                            Text("loop.difference") + Text(verbatim: " " + account.currency + " " + AccountPresentation.amount(AccountPresentation.decimal(difference, digits: account.currencyFractionDigits), locale: locale))
                        }
                        if let remaining = check.unexplainedMinor {
                            Text("loop.check.unexplained") + Text(verbatim: " " + account.currency + " " + AccountPresentation.amount(AccountPresentation.decimal(remaining, digits: account.currencyFractionDigits), locale: locale))
                        }
                        if let note = check.note, !note.isEmpty { Text(verbatim: note) }
                    }.font(ArgusStyle.body(13, relativeTo: .subheadline)).padding(.vertical, 12)
                }
            }
            if page.checksCursor != nil { Button("loop.more") { Task { await loop.more(account, checks: true) } }.disabled(page.loadingMore) }
        }
        .task(id: account.version) { await loop.open(account) }
        .sheet(item: $inspected, onDismiss: {
            if let activity = pendingCorrection { pendingCorrection = nil; loop.record(account, correcting: activity) }
            else if let activity = pendingReturn { pendingReturn = nil; loop.returnPayment(activity) }
        }) { activity in
            NavigationStack {
                ScrollView {
                    FinancialActivityDetailView(loop: loop, activityID: activity.activityId ?? activity.recordId, returnPayment: { current in pendingReturn = current; inspected = nil }) { current in
                        pendingCorrection = current; inspected = nil
                    }.padding(24)
                }.background(ArgusStyle.background)
                    .navigationTitle("loop.activity.title").navigationBarTitleDisplayMode(.inline)
                    .toolbar { ToolbarItem(placement: .cancellationAction) { Button("action.close") { inspected = nil } } }
            }
        }
    }
}

struct FinancialActivityDetailView: View {
    @ObservedObject var loop: FinancialLoopModel
    let activityID: UUID
    var returnPayment: ((FinancialActivityDetail) -> Void)? = nil
    let correct: (FinancialActivityDetail) -> Void
    @State private var detail: FinancialActivityDetail?
    @State private var revisions: [FinancialActivityDetail] = []
    @State private var errorKey: String?
    @Environment(\.locale) private var locale

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            if let detail {
                Text(LocalizedStringKey("loop.kind." + detail.kind.rawValue)).font(ArgusStyle.display(22))
                Text(verbatim: detail.currency + " " + AccountPresentation.amount(detail.amount, locale: locale))
                    .font(ArgusStyle.display(30)).monospacedDigit()
                Text(verbatim: AccountPresentation.date(detail.occurredAt, zone: detail.timeZone, locale: locale))
                if let principal = detail.principalMinor { PlanValueRow(title: "debt.principal", value: minor(principal, detail)) }
                if let interest = detail.interestMinor { PlanValueRow(title: "debt.interest", value: minor(interest, detail)) }
                if let fees = detail.feesMinor { PlanValueRow(title: "debt.fees", value: minor(fees, detail)) }
                if detail.kind == .paymentReversal { Text("debt.return.disclosure") }
                if let category = detail.categoryId { Text(LocalizedStringKey("loop.category." + category)) }
                if let source = detail.sourceId { Text(LocalizedStringKey("loop.source." + source)) }
                if let note = detail.note, !note.isEmpty { Text(verbatim: note) }
                if detail.kind == .refund { Text(detail.purchaseActivityId == nil ? "loop.activity.purchaseNone" : "loop.activity.linkedPurchase") }
                ForEach(detail.legs) { leg in
                    HStack {
                        Text(loop.accountName(leg.accountId)); Spacer()
                        Text(leg.role == "source" ? "loop.activity.from" : leg.role == "destination" ? "loop.activity.to" : "loop.activity.account")
                    }.font(ArgusStyle.body(13, relativeTo: .subheadline))
                }
                if let reason = detail.reason { Text(verbatim: reason) }
                if revisions.count > 1 {
                    Text("loop.revisions").font(ArgusStyle.display(22))
                    ForEach(revisions, id: \.revision) { revision in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(verbatim: revision.currency + " " + AccountPresentation.amount(revision.amount, locale: locale))
                            Text(verbatim: AccountPresentation.date(revision.occurredAt, zone: revision.timeZone, locale: locale))
                            if let reason = revision.reason { Text(verbatim: reason) }
                        }
                    }
                }
                if detail.originalAmountAvailable {
                    if detail.kind == .cardPayment || detail.kind == .debtPayment {
                        Button("debt.return") { if let returnPayment { returnPayment(detail) } else { loop.returnPayment(detail) } }.buttonStyle(PillButtonStyle(primary: false)).disabled(loop.pendingConfirmation != nil).accessibilityIdentifier("activity.return")
                    }
                    Button("loop.correction.title") { correct(detail) }
                        .buttonStyle(PillButtonStyle()).disabled(loop.pendingConfirmation != nil)
                        .accessibilityIdentifier("activity.correct")
                }
            } else if errorKey == nil { ProgressView("accounts.loading") }
            if let errorKey {
                Text(LocalizedStringKey(errorKey)).accessibilityIdentifier("activity.detail.error")
                Button("accounts.retry") { Task { await load() } }.frame(minHeight: 44)
            }
        }.task(id: activityID) { await load() }
            .onChange(of: loop.activityEditor == nil) { _, closed in if closed { Task { await load() } } }
    }
    private func minor(_ value: Int64, _ detail: FinancialActivityDetail) -> String { PlanPresentation.money(String(value), currency: detail.currency, digits: detail.currencyFractionDigits, locale: locale) }
    private func load() async {
        errorKey = nil
        do {
            let current = try await loop.detail(id: activityID)
            detail = current
            revisions = try await loop.detailHistory(current)
        } catch {
            if case SessionFailure.rejected(let status, _) = error, status == 404 || status == 403 {
                detail = nil; errorKey = "search.destination.unavailable"
            } else { errorKey = "loop.error.connection" }
        }
    }
}

extension FinancialActivity: @retroactive Identifiable {
    public var id: UUID { recordId }
}

struct FinancialActivityRow: View {
    let activity: FinancialActivity
    let currency: String
    @Environment(\.locale) private var locale

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: symbol).frame(width: 24)
            VStack(alignment: .leading, spacing: 7) {
                if let note = activity.note, !note.isEmpty { Text(verbatim: note).lineLimit(2) }
                else { Text(LocalizedStringKey("loop.kind." + activity.kind)) }
                if activity.active == false {
                    Text("loop.activity.moved").font(ArgusStyle.body(11, relativeTo: .caption))
                        .foregroundStyle(ArgusStyle.secondary).accessibilityIdentifier("activity.moved")
                }
                Text(verbatim: AccountPresentation.date(activity.occurredAt, zone: activity.timeZone, locale: locale))
                    .font(ArgusStyle.body(11, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
            Spacer(minLength: 8)
            Text(verbatim: sign + currency + " " + AccountPresentation.amount(activity.amount, locale: locale))
                .font(ArgusStyle.body(12, relativeTo: .caption)).monospacedDigit()
        }.font(ArgusStyle.body(14, relativeTo: .subheadline)).padding(.vertical, 16)
            .contentShape(Rectangle())
            .overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }
            .accessibilityElement(children: .combine)
    }
    private var sign: String { activity.balanceMovementMinor > 0 ? "+" : activity.balanceMovementMinor < 0 ? "−" : "" }
    private var symbol: String {
        switch activity.kind {
        case "income": "arrow.down.left"
        case "transfer": "arrow.left.arrow.right"
        case "card_payment", "debt_payment": "creditcard"
        case "payment_reversal": "arrow.uturn.backward"
        case "refund": "arrow.uturn.backward"
        default: "arrow.up.right"
        }
    }
}

struct FinancialEditorPresenter: View {
    @ObservedObject var loop: FinancialLoopModel
    let appearance: AppearancePreference
    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .sheet(item: $loop.activityEditor) { editor in
                FinancialActivityEditorView(model: editor)
                    .preferredColorScheme(appearance.colorScheme).tint(ArgusStyle.ink).foregroundStyle(ArgusStyle.ink)
            }
            .sheet(item: $loop.editor) { editor in
                FinancialEditorView(model: editor)
                    .preferredColorScheme(appearance.colorScheme).tint(ArgusStyle.ink).foregroundStyle(ArgusStyle.ink)
            }
    }
}
