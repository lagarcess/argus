import Foundation

extension ReleaseUpdateKind {
    func title(spanish es: Bool) -> String {
        switch self {
        case .bill(_, let reminder):
            es ? (reminder == .dueToday ? "Vence hoy" : "Vence en 3 días")
                : (reminder == .dueToday ? "Due today" : "Due in 3 days")
        case .draftReady: es ? "Documento listo para revisar" : "Document ready to review"
        case .invitationAccepted: es ? "Invitación aceptada" : "Invitation accepted"
        case .householdAdminHandoff: es ? "Ahora administras el hogar" : "You now manage the household"
        case .householdClosed: es ? "Hogar cerrado" : "Household closed"
        case .movedAccountHistory: es ? "Historial de una cuenta movida" : "History of a moved account"
        case .ownerHistoryRemoved: es ? "Historial retirado" : "History removed"
        case .formerMember: es ? "Un miembro eliminó su cuenta" : "A member deleted their account"
        case .reassignResponsibilities: es ? "Revisa las responsabilidades" : "Review responsibilities"
        case .newPlanOwner: es ? "Ahora administras este plan" : "You now manage this plan"
        }
    }

    func detail(spanish es: Bool) -> String {
        switch self {
        case .bill(let name, _): return name
        case .draftReady:
            return es ? "Revisa el documento antes de confirmar sus registros." : "Review the document before confirming its records."
        case .invitationAccepted(let member):
            return es ? "\(member) aceptó tu invitación. Las cuentas personales siguen siendo privadas hasta que su dueño las comparta."
                : "\(member) accepted your invitation. Personal accounts stay private until their owner shares them."
        case .householdAdminHandoff:
            return es ? "La administración pasó a ti por ser la persona que lleva más tiempo en el hogar."
                : "Administration passed to you as the longest-standing remaining household member."
        case .householdClosed:
            return es ? "El hogar se cerró porque no quedan miembros." : "The household closed because no members remain."
        case .movedAccountHistory(let account):
            return es ? "\(account) se movió fuera del hogar. Este historial se conserva solo para consulta y ya no recibe movimientos nuevos."
                : "\(account) moved out of the household. This history is read-only and no longer receives new activity."
        case .ownerHistoryRemoved:
            return es ? "El dueño eliminó su cuenta. Su historial de cuentas movidas ya no está disponible en el hogar."
                : "The owner deleted their account. Their moved-account history is no longer available in the household."
        case .formerMember(let plan, let balance):
            let base = es ? "Un miembro eliminó su cuenta. Sus montos en «\(plan)» siguen como «Exmiembro», así que tus saldos no cambian."
                : "A member deleted their account. Their amounts in \"\(plan)\" stay as \"Former member,\" so your balances don't change."
            guard let balance else { return base }
            let amount = balance.currency + " " + CanvasMoney.format(balance.amount, currency: balance.currency)
            return base + (es ? " El saldo pendiente con esa persona quedó cerrado (\(amount)). Si ya lo resolvieron fuera de la app, puedes marcarlo como saldado."
                : " The open balance with them is closed (\(amount)). If you settled it outside the app, you can mark it as settled.")
        case .reassignResponsibilities(let plan):
            return es ? "Las responsabilidades futuras de un exmiembro en «\(plan)» volvieron a ti. Revísalas para reasignarlas o repartirlas de nuevo."
                : "A former member's future responsibilities in \"\(plan)\" returned to you. Review them to reassign or split them again."
        case .newPlanOwner(let plan):
            return es ? "Ahora administras «\(plan)». Quien lo creó eliminó su cuenta."
                : "You now manage \"\(plan).\" The person who created it deleted their account."
        }
    }

    var symbol: String {
        switch self {
        case .bill: "calendar"
        case .draftReady: "doc.text"
        case .invitationAccepted, .householdAdminHandoff: "person.2"
        case .householdClosed: "house"
        case .movedAccountHistory: "clock.arrow.circlepath"
        case .ownerHistoryRemoved: "clock.badge.xmark"
        case .formerMember: "person.crop.circle.badge.minus"
        case .reassignResponsibilities, .newPlanOwner: "list.bullet.rectangle"
        }
    }
}
