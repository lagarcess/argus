import Foundation

/// Every word of the saved-receipts surface, Spanish first. These are the founder-approved Consumer words
/// (October 8). The three marked "pending approval" are not in the approved table.
struct SavedReceiptCopy {
    let spanish: Bool

    var title: String { spanish ? "Recibos guardados" : "Saved receipts" }
    /// Pending approval: the approved empty text names a row, "Escanear o subir archivo", that the locked + menu
    /// no longer has (it now offers camera, photo and file rows).
    var empty: String {
        spanish ? "Aún no has guardado recibos. Toca + y escanea o sube un recibo."
                : "You have not saved any receipts yet. Tap + and scan or upload a receipt."
    }
    var saving: String { spanish ? "Guardando recibo…" : "Saving receipt…" }
    var savedTitle: String { spanish ? "Recibo guardado" : "Receipt saved" }
    var savedDetail: String {
        spanish ? "Está en tu cuenta. Puedes verlo o eliminarlo cuando quieras."
                : "It is in your account. You can view or delete it any time."
    }
    var alreadySaved: String { spanish ? "Ya tenías este recibo guardado." : "You already had this receipt saved." }
    var tooLarge: String {
        spanish ? "El archivo pesa más de 10 MB. Elige uno más pequeño." : "The file is larger than 10 MB. Choose a smaller one."
    }
    var wrongType: String { spanish ? "Solo se aceptan PDF, JPEG y PNG." : "Only PDF, JPEG and PNG files are accepted." }
    var limitReached: String {
        spanish ? "Llegaste al límite de recibos por ahora. Inténtalo más tarde." : "You reached the receipt limit for now. Try again later."
    }
    var couldNotSave: String { spanish ? "No pudimos guardar el recibo." : "We could not save the receipt." }
    var retry: String { spanish ? "Reintentar" : "Try again" }
    var view: String { spanish ? "Ver" : "View" }
    var delete: String { spanish ? "Eliminar" : "Delete" }
    var cancel: String { spanish ? "Cancelar" : "Cancel" }
    var done: String { spanish ? "Listo" : "Done" }
    var deleteTitle: String { spanish ? "¿Eliminar este recibo?" : "Delete this receipt?" }
    var deleteMessage: String {
        spanish ? "Se borra de tu cuenta y de nuestros servidores. Tus movimientos no cambian."
                : "It is deleted from your account and our servers. Your activity does not change."
    }
    /// Pending approval: not in the approved table.
    var couldNotOpen: String { spanish ? "No pudimos abrir este recibo." : "We could not open this receipt." }
    /// Pending approval: not in the approved table.
    var couldNotLoad: String { spanish ? "No pudimos cargar tus recibos." : "We could not load your receipts." }

    func failure(_ failure: SavedReceiptFailure) -> String {
        switch failure {
        case .tooLarge: tooLarge
        case .wrongType: wrongType
        case .limitReached: limitReached
        case .couldNotSave: couldNotSave
        }
    }
}
