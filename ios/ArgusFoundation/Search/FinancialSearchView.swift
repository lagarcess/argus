import SwiftUI
import UIKit
import ArgusSession

struct FinancialSearchDestination: View {
    @EnvironmentObject private var auth: ProfileAuthModel
    let active: Bool
    let showProfile: () -> Void
    var body: some View {
        if auth.state == .authenticated, let model = auth.financialSearch, let accounts = auth.accounts, let loop = auth.financialLoop {
            FinancialSearchView(model: model, accounts: accounts, loop: loop, active: active)
        } else {
            VStack(alignment: .leading, spacing: 24) {
                Text("search.title").font(ArgusStyle.display())
                Text("search.gate").foregroundStyle(ArgusStyle.secondary)
                Button("auth.signIn", action: showProfile).buttonStyle(PillButtonStyle())
                Spacer()
            }.padding(24)
        }
    }
}

struct FinancialSearchView: View {
    @ObservedObject var model: FinancialSearchModel
    @ObservedObject var accounts: AccountsModel
    @ObservedObject var loop: FinancialLoopModel
    let active: Bool
    @StateObject private var scroll = SearchScrollOffset()
    @FocusState private var focused: Bool
    private var inputKey: String { (model.ownerID ?? "") + "|" + model.origin.query + "|" + (model.origin.kind?.rawValue ?? "") + "|" + (model.origin.currency ?? "") }
    private var currencies: [String] { Array(Set(accounts.accounts.map(\.currency) + model.items.map(\.currency) + [model.origin.currency].compactMap { $0 })).sorted() }

    var body: some View {
        ZStack {
            VStack(alignment: .leading, spacing: 20) {
                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass").foregroundStyle(ArgusStyle.secondary)
                    TextField("search.placeholder.connected", text: Binding(get: { model.origin.query }, set: { model.update(query: $0) }))
                        .font(ArgusStyle.body(17)).focused($focused).submitLabel(.search)
                        .autocorrectionDisabled().onSubmit { focused = false }.accessibilityIdentifier("search.query")
                    if !model.origin.query.isEmpty {
                        Button { model.update(query: "") } label: { Image(systemName: "xmark.circle.fill") }
                            .frame(width: 44, height: 44).accessibilityLabel("search.clear").accessibilityIdentifier("search.clear")
                    }
                }.frame(minHeight: 48).overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 24) {
                        filter(nil)
                        ForEach(FinancialSearchKind.allCases, id: \.self) { filter($0) }
                    }
                }
                HStack {
                    Text("accounts.currency").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                    Spacer()
                    Picker("accounts.currency", selection: Binding(get: { model.origin.currency }, set: { model.update(currency: .some($0)) })) {
                        Text("search.currency.all").tag(nil as String?)
                        ForEach(currencies, id: \.self) { Text(verbatim: $0).tag(Optional($0)) }
                    }.accessibilityIdentifier("search.currency").frame(minHeight: 44)
                }
                results
            }.padding(.horizontal, 24)
                .opacity(model.destination == nil ? 1 : 0)
                .allowsHitTesting(model.destination == nil)
                .accessibilityHidden(model.destination != nil)
            if let destination = model.destination {
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        Button { Task { await model.back() } } label: { Label("search.back", systemImage: "chevron.left") }
                            .frame(minHeight: 48).accessibilityIdentifier("search.back")
                        switch destination {
                        case .account(let id):
                            if let account = accounts.accounts.first(where: { $0.id == id }) {
                                AccountDetailView(account: account, model: accounts, loop: loop)
                            } else { Text("search.destination.unavailable") }
                        case .activity(let id):
                            FinancialActivityDetailView(loop: loop, activityID: id) { loop.correct($0) }
                        }
                    }.padding(24)
                }.background(ArgusStyle.background).accessibilityIdentifier("search.detail")
            }
        }
        .task(id: inputKey) {
            guard active else { return }
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            await model.activate()
        }
        .onChange(of: active) { _, active in if active { Task { await model.activate() } } else { focused = false } }
    }

    private func filter(_ kind: FinancialSearchKind?) -> some View {
        Button { focused = false; model.update(kind: .some(kind)) } label: {
            Text(LocalizedStringKey("search.filter." + (kind?.rawValue ?? "all")))
                .font(ArgusStyle.body(14)).frame(minWidth: 44, minHeight: 48)
                .foregroundStyle(model.origin.kind == kind ? ArgusStyle.ink : ArgusStyle.secondary)
                .overlay(alignment: .bottom) { Rectangle().fill(model.origin.kind == kind ? ArgusStyle.ink : .clear).frame(height: 1) }
        }.buttonStyle(.plain).accessibilityIdentifier("search.filter." + (kind?.rawValue ?? "all"))
            .accessibilityAddTraits(model.origin.kind == kind ? .isSelected : [])
    }

    private var results: some View {
        ScrollViewReader { reader in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    SearchScrollProbe(controller: scroll).frame(height: 0)
                    if model.loading || model.opening {
                        ProgressView("accounts.loading").padding(.vertical, 12).accessibilityIdentifier("search.loading")
                    }
                    if let error = model.destinationError {
                        Text(LocalizedStringKey(error)).padding(.vertical, 12).accessibilityIdentifier("search.destination.error")
                        Button("action.close") { model.dismissError() }.frame(minHeight: 44)
                    }
                    if let error = model.errorKey {
                        Text(LocalizedStringKey(error)).padding(.vertical, 12).accessibilityIdentifier("search.error")
                        Button("accounts.retry") { Task { await model.refresh() } }.frame(minHeight: 44).accessibilityIdentifier("search.retry")
                    } else if model.items.isEmpty && !model.loading {
                        Text(model.origin.query.isEmpty ? "search.empty.records" : "search.empty.matches")
                            .font(ArgusStyle.body()).padding(.vertical, 24).accessibilityIdentifier("search.empty")
                    }
                    ForEach(FinancialSearchKind.allCases, id: \.self) { kind in
                        let rows = model.items.filter { $0.kind == kind }
                        if !rows.isEmpty {
                            Text(LocalizedStringKey("search.filter." + kind.rawValue)).font(ArgusStyle.display(23))
                                .padding(.top, 18).padding(.bottom, 6).accessibilityAddTraits(.isHeader)
                            ForEach(rows) { hit in
                                Button { focused = false; Task { await model.open(hit, accounts: accounts, loop: loop) } } label: {
                                    FinancialSearchRow(hit: hit)
                                }.buttonStyle(.plain).disabled(model.opening)
                                    .id(hit.id).accessibilityIdentifier("search.row." + hit.id)
                                    .background(GeometryReader { geometry in
                                        Color.clear.preference(key: SearchRowFrames.self, value: [hit.id: geometry.frame(in: .named("search.viewport"))])
                                    })
                            }
                        }
                    }
                    if model.cursor != nil {
                        Button("loop.more") { Task { await model.more() } }.frame(minHeight: 48)
                            .disabled(model.loading).accessibilityIdentifier("search.more")
                    }
                }.padding(.bottom, 24)
            }.coordinateSpace(name: "search.viewport").scrollDismissesKeyboard(.interactively)
                .accessibilityIdentifier("search.results")
                .refreshable { await model.refresh() }
                .onPreferenceChange(SearchRowFrames.self) { frames in
                    scroll.frames = frames
                    if let restoration = model.restoration {
                        if let frame = frames[restoration.anchor],
                           scroll.restore(currentRowOffset: frame.minY, desiredRowOffset: restoration.offset) {
                            model.restored(restoration.id)
                        }
                        return
                    }
                    guard active,
                          let row = frames.filter({ $0.value.maxY > 0 }).min(by: { $0.value.minY < $1.value.minY }) else { return }
                    model.remember(anchor: row.key, offset: row.value.minY)
                }
                .onChange(of: model.restoration) { _, restoration in
                    guard let restoration else { return }
                    Task { @MainActor in
                        await Task.yield()
                        guard model.restoration?.id == restoration.id else { return }
                        if let frame = scroll.frames[restoration.anchor], abs(frame.minY - restoration.offset) < 0.5 {
                            model.restored(restoration.id)
                        } else {
                            reader.scrollTo(restoration.anchor, anchor: .top)
                        }
                    }
                }
        }
    }
}

struct FinancialSearchRow: View {
    let hit: FinancialSearchHit
    @Environment(\.locale) private var locale
    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: symbol).font(.system(size: 19)).frame(width: 26)
            VStack(alignment: .leading, spacing: 6) {
                title.font(ArgusStyle.body(15)).lineLimit(2)
                if hit.archived { Text("accounts.archived").font(ArgusStyle.body(11, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary) }
                if case .activity(let activity, _) = hit {
                    Text(verbatim: AccountPresentation.date(activity.occurredAt, zone: activity.timeZone, locale: locale))
                        .font(ArgusStyle.body(11, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                }
                Text(verbatim: hit.currency + " " + (hit.amount.map { AccountPresentation.amount($0, locale: locale) } ?? NSLocalizedString("accounts.unknown", comment: "")))
                    .font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary).monospacedDigit()
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right").font(.system(size: 11)).foregroundStyle(ArgusStyle.secondary)
        }.padding(.vertical, 18).frame(maxWidth: .infinity, minHeight: 60, alignment: .leading).contentShape(Rectangle())
            .overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }
            .accessibilityElement(children: .combine)
    }
    private var title: Text {
        switch hit {
        case .account(let account): account.nickname.map { Text(verbatim: $0) } ?? Text(LocalizedStringKey("accounts.type." + account.type))
        case .activity(let activity, _): activity.note.map { Text(verbatim: $0) } ?? Text(LocalizedStringKey("loop.kind." + activity.kind.rawValue))
        case .expectation(let expectation): Text(verbatim: expectation.title)
        }
    }
    private var symbol: String {
        switch hit { case .account(let account): AccountPresentation.symbol(account.type); case .activity: "arrow.left.arrow.right"; case .expectation: "calendar" }
    }
}

private struct SearchRowFrames: PreferenceKey {
    static let defaultValue: [String: CGRect] = [:]
    static func reduce(value: inout [String: CGRect], nextValue: () -> [String: CGRect]) { value.merge(nextValue(), uniquingKeysWith: { _, new in new }) }
}

@MainActor
private final class SearchScrollOffset: ObservableObject {
    weak var view: UIScrollView?
    var frames: [String: CGRect] = [:]
    func restore(currentRowOffset: Double, desiredRowOffset: Double) -> Bool {
        guard let view else { return false }
        let delta = currentRowOffset - desiredRowOffset
        if abs(delta) < 0.5 { return true }
        let maximum = max(-view.adjustedContentInset.top, view.contentSize.height - view.bounds.height + view.adjustedContentInset.bottom)
        let y = min(maximum, max(-view.adjustedContentInset.top, view.contentOffset.y + delta))
        // Lazy rows can grow the content bounds after scrollTo. A clamped position
        // is not proof that the saved row offset has been restored.
        if abs(y - view.contentOffset.y) < 0.5 { return false }
        view.setContentOffset(CGPoint(x: view.contentOffset.x, y: y), animated: false)
        return false
    }
}

private struct SearchScrollProbe: UIViewRepresentable {
    let controller: SearchScrollOffset
    func makeUIView(context: Context) -> UIView { UIView() }
    func updateUIView(_ view: UIView, context: Context) {
        DispatchQueue.main.async {
            var parent = view.superview
            while let current = parent {
                if let scroll = current as? UIScrollView { controller.view = scroll; return }
                parent = current.superview
            }
        }
    }
}

struct FinancialDomainPresenter: View {
    @ObservedObject var accounts: AccountsModel
    @ObservedObject var plan: FinancialPlanModel
    @ObservedObject var loop: FinancialLoopModel
    let search: FinancialSearchModel?
    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .sheet(item: $accounts.draft, onDismiss: refreshSearch) { _ in AccountForm(model: accounts) }
            .sheet(item: $plan.draft, onDismiss: refreshSearch) { draft in FinancialExpectationForm(model: plan, draft: draft, loop: loop) }
    }
    private func refreshSearch() { Task { await search?.refresh() } }
}
