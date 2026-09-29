import SwiftUI
import ArgusSession

struct AccountActivityView: View {
    @ObservedObject var loop: FinancialLoopModel
    let account: FinancialAccount
    @State private var pendingCorrection: FinancialActivity?
    @State private var inspected: FinancialActivity?
    @State private var revisions: [FinancialActivity] = []
    @State private var historyFailed = false
    @Environment(\.locale) private var locale

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Button { loop.expense(account) } label: {
                Label("loop.record", systemImage: "plus").frame(maxWidth: .infinity)
            }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("accounts.record")
            Button("loop.check.title") { loop.check(account) }.frame(minHeight: 44)
                .accessibilityIdentifier("accounts.check")
            if let error = loop.errorKey {
                Text(LocalizedStringKey(error)).foregroundStyle(ArgusStyle.secondary)
                Button("accounts.retry") { Task { await loop.open(account) } }
            }
            if !loop.activity.isEmpty {
                Text("loop.recent").font(ArgusStyle.display(22))
                VStack(spacing: 0) {
                    ForEach(loop.activity, id: \.recordId) { activity in
                        Button { inspected = activity } label: {
                            FinancialActivityRow(activity: activity, currency: account.currency)
                        }.buttonStyle(.plain).accessibilityIdentifier("activity.row." + activity.recordId.uuidString)
                    }
                }
            }
            if loop.activityCursor != nil { Button("loop.more") { Task { await loop.more(account, checks: false) } }.disabled(loop.loadingMore) }
            if !loop.checks.isEmpty {
                Text("loop.check.history").font(ArgusStyle.display(22))
                ForEach(loop.checks, id: \.recordId) { check in
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
            if loop.checksCursor != nil { Button("loop.more") { Task { await loop.more(account, checks: true) } }.disabled(loop.loadingMore) }
        }
        .task(id: account.version) { await loop.open(account) }
        .sheet(item: $inspected, onDismiss: {
            if let activity = pendingCorrection { pendingCorrection = nil; loop.expense(account, correcting: activity) }
        }) { activity in
            NavigationStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        FinancialActivityRow(activity: activity, currency: account.currency)
                        Text(verbatim: AccountPresentation.date(activity.occurredAt, zone: activity.timeZone, locale: locale))
                        if let reason = activity.reason { Text(verbatim: reason) }
                        if revisions.count > 1 {
                            Text("loop.revisions").font(ArgusStyle.display(22))
                            ForEach(revisions, id: \.revision) { revision in
                                VStack(alignment: .leading, spacing: 8) {
                                    FinancialActivityRow(activity: revision, currency: account.currency)
                                    if let reason = revision.reason { Text(verbatim: reason) }
                                }
                            }
                        }
                        if historyFailed {
                            Text("loop.error.connection")
                            Button("accounts.retry") { Task { await loadHistory(activity) } }
                        }
                        Button("loop.correction.title") {
                            pendingCorrection = activity
                            inspected = nil
                        }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("activity.correct")
                    }.padding(24)
                }.background(ArgusStyle.background)
                    .navigationTitle("loop.activity.title").navigationBarTitleDisplayMode(.inline)
                    .toolbar { ToolbarItem(placement: .cancellationAction) { Button("action.close") { inspected = nil } } }
            }.task(id: activity.recordId) { await loadHistory(activity) }
        }
    }
    private func loadHistory(_ activity: FinancialActivity) async {
        revisions = []; historyFailed = false
        do { revisions = try await loop.history(account, activity: activity) } catch { historyFailed = true }
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
            Image(systemName: "arrow.up.right").frame(width: 24)
            VStack(alignment: .leading, spacing: 7) {
                if let note = activity.note, !note.isEmpty { Text(verbatim: note).lineLimit(2) }
                else { Text("loop.expense.title") }
                Text(verbatim: AccountPresentation.date(activity.occurredAt, zone: activity.timeZone, locale: locale))
                    .font(ArgusStyle.body(11, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
            Spacer(minLength: 8)
            Text(verbatim: "−" + currency + " " + AccountPresentation.amount(activity.amount, locale: locale))
                .font(ArgusStyle.body(12, relativeTo: .caption)).monospacedDigit()
        }.font(ArgusStyle.body(14, relativeTo: .subheadline)).padding(.vertical, 16)
            .overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }
            .accessibilityElement(children: .combine)
    }
}

struct FinancialEditorPresenter: View {
    @ObservedObject var loop: FinancialLoopModel
    let appearance: AppearancePreference
    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .sheet(item: $loop.editor) { editor in
                FinancialEditorView(model: editor)
                    .preferredColorScheme(appearance.colorScheme).tint(ArgusStyle.ink).foregroundStyle(ArgusStyle.ink)
            }
    }
}
