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
    @State private var groups = CuadraoGroupPreview(
        spanish: !ProcessInfo.processInfo.arguments.contains("--design-english"),
        reset: ProcessInfo.processInfo.arguments.contains("--plan-reset"),
        empty: ProcessInfo.processInfo.arguments.contains("--plan-empty"))
    @State private var receipts = CuadraoReceiptStore(reset: ProcessInfo.processInfo.arguments.contains("--receipt-reset"))
    @State private var receiptRoute: ReceiptRoute?
    @State private var receiptRecoveryError = false
    @State private var profile = CanvasProfileDraft()
    @State private var profilePath: [CanvasProfileRoute] = []
    @State private var updateReadIDs: Set<CanvasUpdate> = []
    @State private var searchChatOrigin = false
    @State private var chatEditing = false
    @State private var voiceProposal: CanvasVoiceProposal?
    @State private var pendingTab: CuadraoTab?
    @State private var navigationScroll = CuadraoNavigationScroll()
    @State private var sheet: HomeSheet?
    @State private var data = CuadraoAccountsPreview(
        populated: (CuadraoCanvas.standalonePreview || ProcessInfo.processInfo.arguments.contains("--home-populated")),
        spanish: !ProcessInfo.processInfo.arguments.contains("--design-english"))
    @State private var accountPath: [UUID] = []
    @State private var archivedID: UUID?
    private let navigationBarHeight: CGFloat = 72
    private let spanish = !ProcessInfo.processInfo.arguments.contains("--design-english")

    private enum HomeSheet: Identifiable {
        case add, updates, spaces, customize, household, gallery
        case account(CanvasAccountSheet)
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
                            if data.selectedSpace.kind == .household {
                                Button { sheet = .household } label: {
                                    PlanAvatarStack(members: data.acceptedHouseholdMembers(spanish: spanish))
                                        .frame(minHeight: 44)
                                }.buttonStyle(.plain)
                                    .accessibilityLabel(spanish ? "Personas del hogar" : "Household members")
                                    .accessibilityValue(String(data.acceptedHouseholdMembers(spanish: spanish).count))
                                    .accessibilityIdentifier("home-household-members")
                            }
                        }
                        ForEach(CuadraoHomeSection.decode(homeOrder)) { section in
                            homeSection(section)
                        }
                        if !data.active.isEmpty {
                            Button { sheet = .customize } label: {
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
                        actions: { sheet = .account($0) }, record: { sheet = .account(.record($0)) })
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
            if (accountPath.isEmpty || selectedTab != .home) &&
                (profilePath.isEmpty || selectedTab != .profile) && !(selectedTab == .assistant && chatEditing) {
            ZStack {
                if chat.voiceMessage.state != .recording {
                    CuadraoNavigationBar(selection: tabSelection,
                        compact: selectedTab == .home && navigationScroll.compact, spanish: spanish)
                        .padding(.horizontal, 20)
                        .frame(height: 64, alignment: .bottom)
                        .padding(.bottom, 8)
                        .transition(.opacity)
                }
            }.frame(height: navigationBarHeight)
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
        .environment(\.receiptWorkspace, receiptWorkspace)
        .receiptPresentation(route: $receiptRoute, workspace: receiptWorkspace, spanish: spanish)
        .task {
            do { try receipts.reconcile(groups: groups, accounts: data) }
            catch { receiptRecoveryError = true }
        }
        .alert(spanish ? "No pudimos recuperar un recibo" : "A receipt could not be recovered", isPresented: $receiptRecoveryError) {
            Button(spanish ? "Listo" : "OK") {}
        } message: { Text(spanish ? "Los archivos siguen en este dispositivo. Revisa tus recibos guardados." : "The files remain on this device. Check your saved receipts.") }
        .onChange(of: selectedTab) { _, tab in
            if tab != .assistant { searchChatOrigin = false }
        }
        .onChange(of: chat.current.id) { _, _ in voiceProposal = nil }
        .onChange(of: data.selectedSpaceID) { _, _ in
            archivedID = nil; accountPath = []; navigationScroll = CuadraoNavigationScroll()
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
        case .overview: if !data.active.isEmpty { CuadraoHomeOverview(data: data, spanish: spanish) }
        case .accounts: accounts
        case .activity: if !data.visibleActivity.isEmpty { activity }
        case .upcoming: if populated && data.selectedSpace.kind == .personal { upcoming }
        }
    }

    private var unreadUpdates: Int {
        CanvasUpdate.available(accounts: data, plans: plans).filter { !updateReadIDs.contains($0) }.count
    }

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 5) {
                Text((spanish ? "Hola" : "Hello") + (profile.preferredName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    ? "" : ", " + profile.preferredName.trimmingCharacters(in: .whitespacesAndNewlines)))
                    .font(.title2.weight(.semibold)).accessibilityIdentifier("home-greeting")
            }
                .contextMenu {
                    Button(spanish ? "Guía visual" : "Visual guide") { sheet = .gallery }
                        .accessibilityIdentifier("cuadrao-gallery-open")
                    Button(spanish ? "Vista previa: primer uso" : "Preview: first use") {
                        populated = false; data.reset(populated: false, spanish: spanish)
                    }
                    Button(spanish ? "Vista previa: Hogar sin cuentas compartidas" : "Preview: household with no shared accounts") {
                        populated = false; data.reset(populated: false, spanish: spanish)
                        data.openHousehold(); data.household = .joined("Alex")
                    }
                    Button(spanish ? "Vista previa: con actividad" : "Preview: with activity") {
                        populated = true; data.reset(populated: true, spanish: spanish)
                    }
                }
            Spacer()
            Button { sheet = .updates } label: {
                Image("CuadraoNotifications").frame(width: 44, height: 44)
                    .overlay(alignment: .topTrailing) {
                        if unreadUpdates > 0 {
                            Text(String(unreadUpdates)).font(.caption2.weight(.medium))
                                .foregroundStyle(WelcomePalette.onAccent).padding(4)
                                .background(WelcomePalette.pine, in: Circle()).accessibilityHidden(true)
                        }
                    }
            }
            .accessibilityLabel(spanish ? "Novedades" : "Updates")
            .accessibilityValue(spanish ? "\(unreadUpdates) sin leer" : "\(unreadUpdates) unread")
            .accessibilityIdentifier("cuadrao.updates.open")
        }
    }

    private var accounts: some View {
        VStack(alignment: .leading, spacing: 12) {
            if !data.active.isEmpty || !data.archived.isEmpty {
                HStack(spacing: 0) {
                    Button { sheet = .account(.manageAccounts(editing: false)) } label: {
                        HStack(spacing: 8) {
                            sectionTitle(spanish ? "Cuentas" : "Accounts")
                            Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.secondary)
                        }.frame(minHeight: 44)
                    }.buttonStyle(.plain).accessibilityIdentifier("home-accounts-open")
                    Spacer()
                    CuadraoSectionAddButton(title: spanish ? "Añadir cuenta" : "Add account") { sheet = .add }
                        .accessibilityIdentifier("home-account-add")
                }
            }
            CuadraoOrderedCollection(items: data.active, spanish: spanish, spacing: 0,
                identifier: { "home-account-" + $0.id.uuidString },
                open: { accountPath.append($0.id) }, edit: { sheet = .account(.rename($0.id)) },
                archive: { data.archive($0.id, true); archivedID = $0.id }, reorder: data.reorder) { account in
                    CanvasAccountRow(account: account, spanish: spanish)
                        .overlay(alignment: .bottom) { Rectangle().fill(.separator).frame(height: 0.5).padding(.leading, 54) }
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
                CuadraoSectionAddButton(title: spanish ? "Añadir movimiento" : "Add activity") {
                    if let account = data.active.first { sheet = .account(.record(account.id)) }
                }.accessibilityIdentifier("home-activity-add")
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

    private var receiptWorkspace: ReceiptWorkspace {
        ReceiptWorkspace(receipts: receipts, groups: groups, accounts: data, chat: chat,
                         capture: { receiptRoute = .capture($0, $1) }, open: { receiptRoute = .review($0) },
                         groupChat: { id in chat.openGroup(id, name: groups.group(id)?.name ?? ""); selectedTab = .assistant })
    }

    @ViewBuilder private func destination(_ tab: CuadraoTab) -> some View {
        if tab == .search {
            CuadraoSearchCanvas(data: data, spanish: spanish, includeExamples: populated,
                plans: plans, chat: chat, openChat: { thread in chat.open(thread); searchChatOrigin = true; selectedTab = .assistant },
                actions: { sheet = .account($0) }, record: { sheet = .account(.record($0)) })
        } else if tab == .assistant {
            CuadraoChatCanvas(store: chat, spanish: spanish, editing: $chatEditing)
                .safeAreaInset(edge: .top, spacing: 0) {
                    if searchChatOrigin {
                        Button { tabSelection.wrappedValue = .search } label: {
                            Label(spanish ? "Volver a Buscar" : "Back to Search", systemImage: "chevron.left")
                                .font(.subheadline).frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                        }.padding(.horizontal, 24).background(WelcomePalette.background)
                            .accessibilityIdentifier("cuadrao.search.return")
                    }
                }
        } else if tab == .profile {
            CuadraoProfileCanvas(spanish: spanish, includeExamples: populated, profile: $profile,
                path: $profilePath, bottomSpace: navigationBarHeight + 8 + (chat.voice.active ? 64 : 0))
        } else if tab == .plan && voiceProposal == nil {
            CuadraoPlanCanvas(store: plans, accounts: data, spanish: spanish,
                bottomSpace: chat.voice.active ? 160 : 90, groups: groups)
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
        case .account(let selection):
            CuadraoAccountModal(data: data, selection: selection, spanish: spanish,
                show: { sheet = .account($0) }, archived: {
                    sheet = nil; accountPath = []; archivedID = $0
                })
        case .updates:
            CuadraoUpdatesCanvas(accounts: data, plans: plans, spanish: spanish,
                readIDs: $updateReadIDs, profile: $profile)
        }
    }
}

#Preview("Home · First use") { CuadraoHomeCanvas().preferredColorScheme(.light) }
