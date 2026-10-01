import SwiftUI

/// Independent native design canvas. Sample values never reach financial services.
struct CuadraoHomeCanvas: View {
    @AppStorage("cuadrao.design.home-section-order") private var homeOrder = CuadraoHomeSection.defaultOrder
    @State private var populated = (CuadraoCanvas.standalonePreview || ProcessInfo.processInfo.arguments.contains("--home-populated"))
    @State private var selectedTab: CuadraoTab = .home
    @State private var chat = CuadraoChatPreview(spanish: !ProcessInfo.processInfo.arguments.contains("--design-english"))
    @Environment(\.dynamicTypeSize) private var typeSize
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var plans = CuadraoPlanPreview(
        spanish: !ProcessInfo.processInfo.arguments.contains("--design-english"),
        reset: ProcessInfo.processInfo.arguments.contains("--plan-reset"),
        empty: ProcessInfo.processInfo.arguments.contains("--plan-empty"))
    @State private var chatEditing = false
    @State private var voiceProposal: CanvasVoiceProposal?
    @State private var pendingTab: CuadraoTab?
    @State private var navigationScroll = CuadraoNavigationScroll()
    @State private var sheet: HomeSheet?
    @State private var data = CuadraoAccountsPreview(
        populated: (CuadraoCanvas.standalonePreview || ProcessInfo.processInfo.arguments.contains("--home-populated")),
        spanish: !ProcessInfo.processInfo.arguments.contains("--design-english"))
    @State private var accountPath: [UUID] = []
    @State private var ordering = false
    @State private var archivedID: UUID?
    @ScaledMetric private var reorderRowHeight = 84
    private let spanish = !ProcessInfo.processInfo.arguments.contains("--design-english")

    private enum HomeSheet: Identifiable {
        case add, options, archived, updates, spaces, customize, household, gallery
        case actions(UUID), rename(UUID), record(UUID)
        var id: String { "home-modal" }
    }

    var body: some View {
        TabView(selection: tabSelection) {
            NavigationStack(path: $accountPath) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 36) {
                        VStack(alignment: .leading, spacing: 18) {
                            header
                            CuadraoSpaceSelector(data: data, spanish: spanish, add: { sheet = .spaces })
                        }
                        ForEach(CuadraoHomeSection.decode(homeOrder)) { section in
                            homeSection(section)
                        }
                        if !data.active.isEmpty {
                            Button { ordering = false; sheet = .customize } label: {
                                Label(spanish ? "Ordenar Inicio" : "Reorder Home", systemImage: "slider.horizontal.3")
                                    .font(.subheadline).frame(maxWidth: .infinity, minHeight: 44)
                            }.foregroundStyle(.secondary).accessibilityIdentifier("customize-home")
                        }
                    }
                    .padding(.horizontal, 24).padding(.top, 28).padding(.bottom, 32)
                }
                .modifier(CuadraoNavigationScrollObserver(scroll: navigationScroll,
                    enabled: selectedTab == .home && sheet == nil && accountPath.isEmpty))
                .safeAreaPadding(.bottom, 80)
                .background(WelcomePalette.background)
                .navigationTitle("").navigationBarTitleDisplayMode(.inline)
                .toolbar(.hidden, for: .navigationBar)
                .navigationDestination(for: UUID.self) { id in
                    CuadraoAccountCanvas(data: data, accountID: id, spanish: spanish,
                        actions: { sheet = .actions($0) }, record: { sheet = .record($0) })
                }
            }
            .toolbar(.hidden, for: .tabBar)
            .tag(CuadraoTab.home)
            ForEach(CuadraoTab.allCases.filter { $0 != .home }) { tab in
                destination(tab).tag(tab)
            }
        }
        .cuadraoScrollBar(edge: .bottom) {
            VStack(spacing: 0) {
            if selectedTab != .assistant && chat.voice.active && chat.voice.presentation != .expanded {
                CuadraoVoiceBar(voice: chat.voice, spanish: spanish)
            }
            if (accountPath.isEmpty || selectedTab != .home) && !(selectedTab == .assistant && chatEditing) {
            ZStack {
                if chat.voiceMessage.state != .recording {
                    CuadraoNavigationBar(selection: tabSelection,
                        compact: selectedTab == .home && navigationScroll.compact, spanish: spanish)
                        .padding(.horizontal, 20)
                        .frame(height: 64, alignment: .bottom)
                        .padding(.bottom, 8)
                        .transition(.opacity)
                }
            }.frame(height: 72)
                .animation(reduceMotion ? nil : .easeOut(duration: 0.18), value: chat.voiceMessage.state == .recording)
            }
            }
        }
        .cuadraoSoftScrollEdges()
        .overlay(alignment: .bottom) {
            if chat.voiceMessage.state == .recording {
                GeometryReader { geometry in
                    CuadraoVoiceRecordingOverlay(message: chat.voiceMessage, spanish: spanish)
                        .frame(height: typeSize.isAccessibilitySize ? geometry.size.height : min(460, geometry.size.height))
                        .frame(maxHeight: .infinity, alignment: .bottom)
                }.ignoresSafeArea(edges: .bottom)
                    .allowsHitTesting(chat.voiceMessage.locked && !chat.voiceMessage.held)
            }
        }
        .fullScreenCover(isPresented: Binding(
            get: { chat.voice.active && chat.voice.presentation == .expanded },
            set: { if !$0 && chat.voice.active && chat.voice.presentation == .expanded { chat.voice.presentation = .compact } })) {
            CuadraoLiveVoiceCanvas(chat: chat, spanish: spanish, keyboard: {
                selectedTab = .assistant
                chat.voice.presentation = .keyboard
            }, showProposal: {
                voiceProposal = .proposed
                selectedTab = .plan
                chat.voice.presentation = .compact
            })
        }
        .confirmationDialog(spanish ? "¿Terminar el chat temporal?" : "End temporary chat?",
            isPresented: Binding(get: { pendingTab != nil }, set: { if !$0 { pendingTab = nil } }), titleVisibility: .visible) {
            Button(spanish ? "Terminar y salir" : "End and leave", role: .destructive) {
                let destination = pendingTab; chat.leaveTemporary(for: .returnToRegular); pendingTab = nil
                if let destination { selectedTab = destination }
            }
            Button(spanish ? "Seguir aquí" : "Stay here", role: .cancel) { pendingTab = nil }
        } message: { Text(spanish ? "Se descartará el contenido temporal. Tu chat anterior quedará intacto." : "Temporary content will be discarded. Your previous chat stays intact.") }
        .tint(WelcomePalette.pine).foregroundStyle(WelcomePalette.ink)
        .sheet(item: $sheet) { item in modal(item) }
        .onChange(of: chat.current.id) { _, _ in voiceProposal = nil }
        .onChange(of: data.selectedSpaceID) { _, _ in
            ordering = false; archivedID = nil; accountPath = []; navigationScroll = CuadraoNavigationScroll()
        }
        .overlay(alignment: .bottom) {
            if let archivedID {
                HStack {
                    Text(spanish ? "Cuenta archivada" : "Account archived")
                    Spacer()
                    Button(spanish ? "Deshacer" : "Undo") {
                        data.archive(archivedID, false); self.archivedID = nil
                    }
                    Button { self.archivedID = nil } label: { Image(systemName: "xmark").frame(width: 44, height: 44) }
                        .accessibilityLabel(spanish ? "Cerrar" : "Close")
                }.font(.subheadline).padding(.leading, 20).padding(.trailing, 6)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
                    .padding(.horizontal, 20).padding(.bottom, 90)
            }
        }
    }

    private var tabSelection: Binding<CuadraoTab> {
        Binding(get: { selectedTab }, set: { next in
            if selectedTab == .assistant && next != .assistant && chat.hasTemporaryContent { pendingTab = next }
            else {
                if selectedTab == .assistant && next != .assistant && chat.temporary { chat.leaveTemporary(for: .returnToRegular) }
                selectedTab = next
            }
        })
    }

    @ViewBuilder private func homeSection(_ section: CuadraoHomeSection) -> some View {
        switch section {
        case .overview: if !data.active.isEmpty { CuadraoHomeOverview(data: data, spanish: spanish, openPlan: { selectedTab = .plan }) }
        case .accounts: accounts
        case .activity: if !data.visibleActivity.isEmpty { activity }
        case .upcoming: if populated && data.selectedSpace.kind == .personal { upcoming }
        }
    }

    private var header: some View {
        HStack {
            CuadraoBrand()
                .contextMenu {
                    Button(spanish ? "Guía visual" : "Visual guide") { sheet = .gallery }
                        .accessibilityIdentifier("cuadrao-gallery-open")
                    Button(spanish ? "Vista previa: primer uso" : "Preview: first use") {
                        populated = false; data.reset(populated: false, spanish: spanish); ordering = false
                    }
                    Button(spanish ? "Vista previa: Hogar sin cuentas compartidas" : "Preview: household with no shared accounts") {
                        populated = false; data.reset(populated: false, spanish: spanish)
                        data.openHousehold(); data.household = .joined("Alex")
                    }
                    Button(spanish ? "Vista previa: con actividad" : "Preview: with activity") {
                        populated = true; data.reset(populated: true, spanish: spanish); ordering = false
                    }
                }
            Spacer()
            Button { sheet = .updates } label: {
                Image("CuadraoNotifications").frame(width: 44, height: 44)
            }
            .accessibilityLabel(spanish ? "Novedades" : "Updates")
        }
    }

    private var accounts: some View {
        VStack(alignment: .leading, spacing: 12) {
            if data.selectedSpace.kind == .household && !data.active.isEmpty {
                Button { sheet = .household } label: {
                    Label(spanish ? "Personas" : "People", systemImage: "person.2")
                        .font(.subheadline).frame(minHeight: 44)
                }
            }
            if !data.active.isEmpty || !data.archived.isEmpty {
                HStack(spacing: 0) {
                    sectionTitle(spanish ? "Cuentas" : "Accounts")
                    Spacer()
                    if ordering {
                        Button(spanish ? "Listo" : "Done") { ordering = false }
                            .font(.subheadline.weight(.medium)).frame(minHeight: 44)
                    } else {
                        Button { sheet = .add } label: { Image(systemName: "plus").frame(width: 44, height: 44) }
                            .accessibilityLabel(spanish ? "Añadir cuenta" : "Add account")
                        Button { sheet = .options } label: { Image(systemName: "ellipsis").frame(width: 44, height: 44) }
                            .accessibilityLabel(spanish ? "Opciones de cuentas" : "Account options")
                    }
                }
            }
            if ordering {
                List {
                    ForEach(data.active) { account in
                        CanvasAccountRow(account: account, spanish: spanish)
                            .padding(.trailing, 20)
                            .listRowInsets(EdgeInsets()).listRowBackground(WelcomePalette.background)
                            .frame(height: reorderRowHeight)
                    }.onMove { from, to in data.move(from: from, to: to) }
                }.listStyle(.plain).scrollDisabled(true)
                    .environment(\.editMode, .constant(.active))
                    .frame(height: reorderRowHeight * CGFloat(data.active.count))
            } else {
                ForEach(data.active) { account in
                    CanvasAccountRow(account: account, spanish: spanish)
                        .gesture(LongPressGesture(minimumDuration: 0.45).exclusively(before: TapGesture()).onEnded { gesture in
                            switch gesture {
                            case .first: sheet = .actions(account.id)
                            case .second: accountPath.append(account.id)
                            }
                        })
                        .accessibilityElement(children: .combine)
                        .accessibilityAddTraits(.isButton)
                        .accessibilityAction { accountPath.append(account.id) }
                        .accessibilityAction(named: Text(spanish ? "Opciones de cuenta" : "Account actions")) { sheet = .actions(account.id) }
                        .overlay(alignment: .bottom) { Divider().padding(.leading, 54) }
                }
            }
            if data.active.isEmpty { firstAccount }
        }
    }

    private var firstAccount: some View {
        CuadraoHomeEmptyState(data: data, spanish: spanish,
            addAccount: { sheet = .add }, household: { sheet = .household })
    }

    private var activity: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                sectionTitle(spanish ? "Movimientos" : "Activity")
                Spacer()
                Button { if let account = data.active.first { sheet = .record(account.id) } } label: {
                    Image(systemName: "plus").frame(width: 44, height: 44)
                }.accessibilityLabel(spanish ? "Añadir movimiento" : "Add activity")
            }
            Text(spanish ? "Hoy" : "Today").font(.footnote).foregroundStyle(.secondary)
            ForEach(data.visibleActivity.prefix(3)) { entry in
                if let account = data.account(entry.accountID) {
                    feedRow(entry.title, detail: account.displayName(spanish),
                        amount: (entry.income ? "+" : "−") + CanvasMoney.format(entry.amount, currency: account.currency),
                        icon: entry.income ? "arrow.down.left" : "arrow.up.right")
                }
            }
        }
    }

    private var upcoming: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                sectionTitle(spanish ? "Próximamente" : "Coming up")
                Spacer()
                Button(spanish ? "Ver plan" : "View plan") { selectedTab = .plan }
                    .font(.subheadline).frame(minHeight: 44)
            }
            feedRow("Internet", detail: spanish ? "Mañana · Previsto" : "Tomorrow · Planned", amount: "1,500.00", icon: "wifi")
        }
    }

    private func feedRow(_ title: String, detail: String, amount: String, icon: String) -> some View {
        HStack(alignment: .center, spacing: 14) {
            Image(systemName: icon).font(.body).frame(width: 28).foregroundStyle(.secondary).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 5) {
                Text(title).font(.body)
                Text(detail).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Text(amount).font(CuadraoTypography.rowAmount)
        }.padding(.vertical, 6)
    }

    private func sectionTitle(_ title: String) -> some View {
        Text(title).font(CuadraoTypography.section).accessibilityAddTraits(.isHeader)
    }

    @ViewBuilder private func destination(_ tab: CuadraoTab) -> some View {
        if tab == .search {
            CuadraoSearchCanvas(data: data, spanish: spanish, includeExamples: populated,
                chat: chat, openChat: { thread in chat.open(thread); selectedTab = .assistant },
                actions: { sheet = .actions($0) }, record: { sheet = .record($0) })
        } else if tab == .assistant {
            CuadraoChatCanvas(store: chat, spanish: spanish, editing: $chatEditing)
        } else if tab == .profile {
            CuadraoProfileCanvas(spanish: spanish, includeExamples: populated)
                .safeAreaPadding(.bottom, chat.voice.active ? 144 : 80)
        } else if tab == .plan && voiceProposal == nil {
            CuadraoPlanCanvas(store: plans, accounts: data, spanish: spanish,
                bottomSpace: chat.voice.active ? 160 : 90)
        } else if voiceProposal != nil {
            CuadraoVoiceProposalCanvas(state: $voiceProposal, spanish: spanish)
        } else {
        NavigationStack {
            ContentUnavailableView(tab.title(spanish: spanish), systemImage: tab.symbol,
                description: Text(spanish ? "Este espacio se diseña después de Inicio." : "This space will be designed after Home."))
                .background(WelcomePalette.background)
        }
        .toolbar(.hidden, for: .tabBar)
        }
    }

    @ViewBuilder private func modal(_ item: HomeSheet) -> some View {
        switch item {
        case .gallery: CuadraoDesignGallery()
        case .household: CuadraoHouseholdSheet(data: data, spanish: spanish)
        case .customize: CuadraoHomeLayoutSheet(savedOrder: $homeOrder, spanish: spanish)
        case .spaces: CuadraoSpacesSheet(data: data, spanish: spanish)
        case .add: CuadraoFirstAccountSheet(data: data, spanish: spanish)
        case .archived: CuadraoArchivedAccounts(data: data, spanish: spanish)
        case .options:
            VStack(alignment: .leading, spacing: 8) {
                Text(spanish ? "Cuentas" : "Accounts").font(.title3.weight(.medium)).padding(.bottom, 12)
                CanvasActionRow(title: spanish ? "Ordenar cuentas" : "Reorder accounts", symbol: "line.3.horizontal") {
                    sheet = nil; ordering = true
                }.disabled(data.active.count < 2)
                Divider()
                CanvasActionRow(title: spanish ? "Cuentas archivadas" : "Archived accounts", symbol: "archivebox") { sheet = .archived }
            }.padding(28).presentationDetents([.height(250)]).presentationDragIndicator(.visible)
        case .actions(let id):
            if let account = data.account(id) {
                CuadraoAccountActions(account: account, spanish: spanish,
                    rename: { sheet = .rename(id) }, record: { sheet = .record(id) }, archive: {
                        data.archive(id, true); sheet = nil; accountPath = []; archivedID = id
                    })
            }
        case .rename(let id):
            if let account = data.account(id) { CuadraoRenameAccount(data: data, account: account, spanish: spanish) }
        case .record(let id):
            if let account = data.account(id) { CuadraoTransactionCanvas(data: data, account: account, spanish: spanish) }
        case .updates:
            NavigationStack {
                ContentUnavailableView {
                    Label {
                        Text(spanish ? "Novedades" : "Updates")
                    } icon: {
                        Image("CuadraoNotifications").resizable().scaledToFit().frame(width: 40, height: 40)
                    }
                } description: {
                    Text(spanish ? "Este espacio se diseña después de Inicio." : "This space will be designed after Home.")
                }
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button(spanish ? "Listo" : "Done") { sheet = nil } } }
            }
        }
    }
}

#Preview("Home · First use") { CuadraoHomeCanvas().preferredColorScheme(.light) }
