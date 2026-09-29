import SwiftUI
import ArgusSession

struct AccountsDestination: View {
    @EnvironmentObject private var auth: ProfileAuthModel
    let showProfile: () -> Void
    let showSample: () -> Void

    var body: some View {
        if !auth.enabled {
            AccountsSampleView(showSample: showSample)
        } else if auth.state == .authenticated, let model = auth.accounts {
            AccountsView(model: model)
        } else {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    PersonalContext()
                    Text("accounts.gate.title").font(ArgusStyle.display())
                    Text("accounts.gate.body").foregroundStyle(ArgusStyle.secondary)
                    Button("auth.signIn", action: showProfile).buttonStyle(PillButtonStyle())
                }.padding(24)
            }
        }
    }
}

struct AccountsView: View {
    @ObservedObject var model: AccountsModel
    @Environment(\.locale) private var locale

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                PersonalContext()
                if let account = model.selected {
                    Button { model.back() } label: { Label("accounts.back", systemImage: "chevron.left") }
                        .frame(minHeight: 48).accessibilityIdentifier("accounts.back")
                    detail(account)
                } else {
                    if model.accounts.isEmpty, !model.busy {
                        Text("accounts.empty.title").font(ArgusStyle.display())
                        Text("accounts.empty.body").foregroundStyle(ArgusStyle.secondary)
                    }
                    VStack(spacing: 0) {
                        ForEach(model.accounts, id: \.id) { account in
                            Button { Task { await model.open(account) } } label: {
                                AccountSummary(account: account)
                                    .padding(.vertical, 16)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }
                            }.buttonStyle(.plain).accessibilityIdentifier("accounts.row.\(account.id)")
                        }
                    }
                    Button("accounts.add") { model.create() }
                        .buttonStyle(PillButtonStyle()).accessibilityIdentifier("accounts.add")
                }
                if let error = model.errorKey, model.draft == nil {
                    Text(LocalizedStringKey(error)).accessibilityIdentifier("accounts.error")
                    Button("accounts.retry") { Task { await model.load() } }.frame(minHeight: 48)
                }
                if model.busy { ProgressView("accounts.loading") }
                Text("accounts.scope").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }.padding(24)
        }
        .refreshable { await model.load() }
        .task(id: model.identity?.revision) { await model.load() }
        .sheet(item: $model.draft) { _ in AccountForm(model: model) }
    }

    @ViewBuilder private func detail(_ account: FinancialAccount) -> some View {
        AccountSummary(account: account, large: true)
        Button("accounts.edit") { model.edit(account) }.buttonStyle(PillButtonStyle(primary: false))
            .accessibilityIdentifier("accounts.edit")
        Button(account.opening == nil ? "accounts.opening.add" : "accounts.opening.correct") { model.opening(account) }
            .buttonStyle(PillButtonStyle()).accessibilityIdentifier("accounts.opening")
        if let opening = account.opening {
            Text("accounts.history").font(ArgusStyle.display(23)).accessibilityAddTraits(.isHeader)
            ForEach(opening.revisions, id: \.revision) { revision in
                VStack(alignment: .leading, spacing: 8) {
                    Text(verbatim: account.currency + " " + AccountPresentation.amount(revision.amount, locale: locale))
                        .monospacedDigit()
                    Text(verbatim: AccountPresentation.date(revision.asOf, zone: revision.timeZone, locale: locale))
                    Text(verbatim: revision.timeZone).font(ArgusStyle.body(12, relativeTo: .caption))
                    if let reason = revision.reason { Text(verbatim: reason) }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
                    .accessibilityElement(children: .combine)
            }
        }
        Button(account.archived ? "accounts.restore" : "accounts.archive") { Task { await model.archive(account) } }
            .buttonStyle(PillButtonStyle(primary: false)).disabled(model.busy).accessibilityIdentifier("accounts.archive")
    }
}

struct AccountSummary: View {
    let account: FinancialAccount
    var large = false
    @Environment(\.locale) private var locale
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let nickname = account.nickname { Text(verbatim: nickname).font(large ? ArgusStyle.display() : ArgusStyle.body()) }
            Text(LocalizedStringKey("accounts.type." + account.type)).foregroundStyle(ArgusStyle.secondary)
            if account.balance.state == .known, let amount = account.balance.amount {
                Text(verbatim: account.currency + " " + AccountPresentation.amount(amount, locale: locale))
                    .font(large ? ArgusStyle.display(30) : ArgusStyle.body()).monospacedDigit()
            } else { Text("accounts.unknown") }
            if account.nature == "liability" { Text("accounts.signedBalance").font(ArgusStyle.body(12, relativeTo: .caption)) }
            if account.archived { Text("accounts.archived").font(ArgusStyle.body(12, relativeTo: .caption)) }
        }.fixedSize(horizontal: false, vertical: true).accessibilityElement(children: .combine)
    }
}

/// Separator-only presentation preserves every digit without floating-point conversion.
enum AccountPresentation {
    static func amount(_ exact: String, locale: Locale) -> String {
        let pieces = exact.split(separator: ".", omittingEmptySubsequences: false)
        var whole = String(pieces[0]); let negative = whole.hasPrefix("-")
        if negative { whole.removeFirst() }
        let groups = stride(from: whole.count, to: 0, by: -3).map { end -> String in
            let lower = whole.index(whole.startIndex, offsetBy: max(0, end - 3))
            let upper = whole.index(whole.startIndex, offsetBy: end)
            return String(whole[lower..<upper])
        }.reversed().joined(separator: locale.groupingSeparator ?? ",")
        return (negative ? "-" : "") + groups + (pieces.count > 1 ? (locale.decimalSeparator ?? ".") + pieces[1] : "")
    }
    static func date(_ exact: String, zone: String, locale: Locale) -> String {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fractional = parser.date(from: exact)
        parser.formatOptions = [.withInternetDateTime]
        guard let date = fractional ?? parser.date(from: exact), let timeZone = TimeZone(identifier: zone) else { return exact }
        let formatter = DateFormatter(); formatter.locale = locale; formatter.timeZone = timeZone
        formatter.dateStyle = .medium; formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}
