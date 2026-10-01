import SwiftUI

struct CuadraoGroupDetail: View {
    let store: CuadraoGroupPreview
    let groupID: UUID
    let spanish: Bool
    var bottomSpace: CGFloat = 90
    @State private var section = 0
    @State private var sheet: GroupSheet?
    @State private var people = 8.0
    @State private var didSave = false
    @Environment(\.dismiss) private var dismiss
    private var group: PlanGroup? { store.group(groupID) }
    private enum GroupSheet: Identifiable {
        case invite, edit, expense(PlanSharedExpense?), settle
        var id: String { switch self { case .invite: "invite"; case .edit: "edit"; case .expense: "expense"; case .settle: "settle" } }
    }
    var body: some View {
        Group {
            if let group {
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        hero(group)
                        Picker(spanish ? "Ver" : "View", selection: $section) {
                            Text(spanish ? "El plan" : "The plan").tag(0)
                            Text(group.kind == .trip ? (spanish ? "Gastos" : "Expenses") : (spanish ? "Aportes" : "Contributions")).tag(1)
                            Text(spanish ? "Personas" : "People").tag(2)
                        }.pickerStyle(.segmented).accessibilityIdentifier("group-sections")
                        if section == 0 { overview(group) }
                        if section == 1 { expenses(group) }
                        if section == 2 { members(group) }
                        Text(spanish ? "Vista previa local · no envía invitaciones ni mueve dinero" : "Local preview · no invitations sent or money moved")
                            .font(.caption2).foregroundStyle(.secondary).frame(maxWidth: .infinity).multilineTextAlignment(.center)
                    }.padding(.horizontal, 24).padding(.bottom, bottomSpace)
                }.background(WelcomePalette.background).cuadraoSoftScrollEdges()
                    .toolbar {
                        ToolbarItem(placement: .topBarTrailing) {
                            Button { sheet = .invite } label: { Image(systemName: "person.badge.plus").frame(width: 44, height: 44) }
                                .accessibilityLabel(spanish ? "Invitar al grupo" : "Invite to group").accessibilityIdentifier("group-invite")
                        }
                        ToolbarItem(placement: .topBarTrailing) {
                            Menu {
                                Button(spanish ? "Editar grupo" : "Edit group", systemImage: "pencil") { sheet = .edit }
                                Button(spanish ? "Archivar" : "Archive", systemImage: "archivebox") { store.archive(group.id, true); dismiss() }
                            } label: { Image(systemName: "ellipsis").frame(width: 44, height: 44) }.accessibilityIdentifier("group-options")
                        }
                    }
                    .sheet(item: $sheet) { route in
                        switch route {
                        case .invite: CuadraoGroupInvitation(store: store, groupID: group.id, spanish: spanish)
                        case .edit: CuadraoGroupEditor(store: store, spanish: spanish, initial: group)
                        case .expense(let entry): CuadraoGroupExpenseEditor(store: store, groupID: group.id, initial: entry, spanish: spanish)
                        case .settle: CuadraoGroupSettlement(store: store, groupID: group.id, spanish: spanish)
                        }
                    }
                    .onAppear { people = Double(group.expectedPeople) }
            }
        }.navigationTitle("").navigationBarTitleDisplayMode(.inline).toolbar(.visible, for: .navigationBar)
            .sensoryFeedback(.success, trigger: didSave) { _, new in new }
    }
    private func hero(_ group: PlanGroup) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            PlanGroupArtwork(look: group.look, progress: group.kind == .saving ? group.progress : nil, cover: group.cover)
                .frame(height: 145).clipShape(RoundedRectangle(cornerRadius: 28))
                .overlay(alignment: .bottomLeading) { PlanAvatarStack(members: group.members).padding(16) }
            Text(group.name).font(CuadraoTypography.screen)
            Text(spanish ? "\(group.members.count) personas · \(group.kind.title(true))" : "\(group.members.count) people · \(group.kind.title(false))")
                .font(.caption).foregroundStyle(.secondary)
        }
    }
    @ViewBuilder private func overview(_ group: PlanGroup) -> some View {
        if group.kind == .saving {
            VStack(alignment: .leading, spacing: 10) {
                Text(PlanFormat.amount(Double(group.total) / 100, currency: group.currency)).font(.system(.largeTitle, design: .rounded)).monospacedDigit()
                Text(spanish ? "reunido de \(PlanFormat.amount(Double(group.estimatedCents) / 100, currency: group.currency))" : "saved of \(PlanFormat.amount(Double(group.estimatedCents) / 100, currency: group.currency))").font(.subheadline).foregroundStyle(.secondary)
                ProgressView(value: group.progress).tint(group.look.color)
                Text(group.progress >= 1 ? (spanish ? "Llegamos. Qué buen equipo." : "We made it. What a team.") : (spanish ? "Cada aporte abre camino." : "Every contribution moves us forward."))
                    .font(.system(.title3, design: .serif)).foregroundStyle(group.look.color)
            }
        } else { balances(group) }
        VStack(alignment: .leading, spacing: 14) {
            Text(spanish ? "¿Y si se suma alguien más?" : "What if someone else joins?").font(CuadraoTypography.section)
            Text(PlanFormat.amount(Double(group.estimatedCents) / 100 / people, currency: group.currency)).font(.system(size: 30, design: .rounded)).monospacedDigit().contentTransition(.numericText())
                .accessibilityIdentifier("group-estimate-per-person")
            Text(spanish ? "por persona · \(Int(people)) personas previstas" : "per person · \(Int(people)) expected people").font(.subheadline).foregroundStyle(.secondary)
            Slider(value: $people, in: 1...50, step: 1).tint(group.look.color).accessibilityLabel(spanish ? "Personas previstas" : "Expected people").accessibilityIdentifier("group-people-slider")
            Text(spanish ? "Estimado total: \(PlanFormat.amount(Double(group.estimatedCents) / 100, currency: group.currency)). Reparto igual; todavía no es una deuda." : "Total estimate: \(PlanFormat.amount(Double(group.estimatedCents) / 100, currency: group.currency)). Equal split; this isn't a debt yet.")
                .font(.caption).foregroundStyle(.secondary)
            if Int(people) != group.expectedPeople {
                Button(spanish ? "Guardar estimación" : "Save estimate") {
                    var updated = group; updated.expectedPeople = Int(people); store.save(updated); didSave = true
                }.font(.subheadline.weight(.medium)).frame(minHeight: 44).accessibilityIdentifier("group-save-estimate")
            }
        }.padding(20).background(group.look.color.opacity(0.07), in: RoundedRectangle(cornerRadius: 26))
        PlanPrimaryButton(title: group.kind == .trip ? (spanish ? "Añadir gasto" : "Add expense") : (spanish ? "Registrar aporte" : "Record contribution"), symbol: "plus") { sheet = .expense(nil) }
            .accessibilityIdentifier("group-add-expense")
    }
    private func balances(_ group: PlanGroup) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(spanish ? "Tu parte" : "Your share").font(.subheadline).foregroundStyle(.secondary)
                    Text(PlanFormat.amount(Double(group.share(group.me)) / 100, currency: group.currency)).font(.system(size: 30, design: .rounded)).monospacedDigit().accessibilityIdentifier("group-own-share")
                }
                Spacer()
                Image(systemName: "person.crop.circle").font(.title).foregroundStyle(group.look.color)
            }
            HStack {
                metric(spanish ? "Total del grupo" : "Group total", cents: group.total, group: group)
                Spacer()
                metric(spanish ? "Pagaste" : "You paid", cents: group.paid(group.me), group: group)
            }
            Divider()
            HStack {
                let balance = group.balance(group.me)
                Text(balance == 0 ? (spanish ? "Todo cuadrado" : "All settled") : balance > 0 ? (spanish ? "Por recuperar" : "To receive") : (spanish ? "Por pagar" : "To pay"))
                Spacer()
                Text(PlanFormat.amount(Double(abs(balance)) / 100, currency: group.currency)).monospacedDigit()
            }.font(.subheadline.weight(.medium)).foregroundStyle(group.look.color).accessibilityIdentifier("group-outstanding")
            if group.members.contains(where: { group.balance($0.id) < 0 }) {
                Button(spanish ? "Ver cómo cuadramos" : "See how to settle up") { sheet = .settle }
                    .font(.subheadline).frame(minHeight: 44).accessibilityIdentifier("group-settle")
            }
        }
    }
    private func metric(_ label: String, cents: Int, group: PlanGroup) -> some View {
        VStack(alignment: .leading, spacing: 6) { Text(label).font(.caption).foregroundStyle(.secondary); Text(PlanFormat.amount(Double(cents) / 100, currency: group.currency)).font(.subheadline.weight(.medium)).monospacedDigit() }
    }
    private func expenses(_ group: PlanGroup) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            PlanPrimaryButton(title: group.kind == .trip ? (spanish ? "Añadir gasto" : "Add expense") : (spanish ? "Registrar aporte" : "Record contribution"), symbol: "plus") { sheet = .expense(nil) }
                .accessibilityIdentifier("group-add-expense")
            if group.expenses.isEmpty { Text(spanish ? "Aquí empieza la historia del plan." : "Your plan's story starts here.").foregroundStyle(.secondary) }
            ForEach(group.expenses.reversed()) { entry in
                Button { sheet = .expense(entry) } label: {
                    HStack(spacing: 12) {
                        Image(systemName: entry.draft ? "doc.badge.clock" : group.kind == .saving ? "leaf" : "receipt").frame(width: 42, height: 42).background(group.look.color.opacity(0.1), in: RoundedRectangle(cornerRadius: 14))
                        VStack(alignment: .leading, spacing: 5) {
                            Text(entry.title).foregroundStyle(WelcomePalette.ink)
                            Text(entry.draft ? (spanish ? "Borrador privado · repartir después" : "Private draft · split later") : "\(group.members.first { $0.id == entry.payer }?.name ?? "") · \(spanish ? "registrado" : "recorded")")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Text(entry.draft && entry.cents == 0 ? (spanish ? "Total pendiente" : "Total pending") : PlanFormat.amount(Double(entry.cents) / 100, currency: group.currency)).font(.subheadline).foregroundStyle(WelcomePalette.ink)
                    }.frame(minHeight: 64)
                }.buttonStyle(.plain).accessibilityIdentifier("group-entry-\(entry.draft ? "draft" : "recorded")")
            }
            if !group.repayments.isEmpty {
                Text(spanish ? "Reembolsos registrados" : "Recorded repayments").font(.headline)
                ForEach(group.repayments) { entry in
                    HStack {
                        Text("\(group.members.first { $0.id == entry.from }?.name ?? "") → \(group.members.first { $0.id == entry.to }?.name ?? "")")
                        Spacer(); Text(PlanFormat.amount(Double(entry.cents) / 100, currency: group.currency))
                        Button { var updated = group; updated.repayments.removeAll { $0.id == entry.id }; store.save(updated) } label: { Image(systemName: "arrow.uturn.backward").frame(width: 44, height: 44) }.accessibilityLabel(spanish ? "Deshacer reembolso" : "Undo repayment")
                    }.font(.subheadline)
                }
            }
        }
    }
    private func members(_ group: PlanGroup) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            ForEach(Array(group.members.enumerated()), id: \.element.id) { index, member in
                HStack(spacing: 12) {
                    PlanMemberAvatar(member: member, index: index)
                    Text(member.name); Spacer()
                    VStack(alignment: .trailing, spacing: 4) {
                        Text(PlanFormat.amount(Double(group.kind == .saving ? group.paid(member.id) : abs(group.balance(member.id))) / 100, currency: group.currency)).font(.subheadline)
                        Text(group.kind == .saving ? (spanish ? "aportado" : "contributed") : group.balance(member.id) > 0 ? (spanish ? "por recuperar" : "to receive") : group.balance(member.id) < 0 ? (spanish ? "por pagar" : "to pay") : (spanish ? "al día" : "settled")).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            Button { sheet = .invite } label: { Label(spanish ? "Invitar a alguien" : "Invite someone", systemImage: "person.badge.plus").frame(minHeight: 44) }
            Text(spanish ? "Solo compartimos este plan. Las cuentas, otros planes y chats de cada quien siguen privados." : "Only this plan is shared. Everyone's accounts, other plans and chats stay private.").font(.caption).foregroundStyle(.secondary)
        }
    }
}
