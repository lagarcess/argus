import SwiftUI

struct CanvasChatAttachmentChip: View {
    let item: CanvasChatAttachment
    var spanish = true
    var remove: (() -> Void)? = nil
    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: item.symbol).foregroundStyle(WelcomePalette.pine)
            Text(item.name).font(.footnote).lineLimit(2)
            if let remove {
                Button(action: remove) { Image(systemName: "xmark").frame(width: 44, height: 44) }
                    .accessibilityLabel(Text(item.name + " · " + (spanish ? "Quitar" : "Remove")))
            }
        }.padding(.leading, 12).padding(.trailing, remove == nil ? 12 : 0).padding(.vertical, remove == nil ? 12 : 0)
            .background(WelcomePalette.background, in: RoundedRectangle(cornerRadius: 14))
            .overlay { RoundedRectangle(cornerRadius: 14).stroke(WelcomePalette.separator, lineWidth: 1) }
    }
}

enum CanvasChatCalculation {
    static let monthly = 3_000
    static let months = 6
    static var total: Int { monthly * months }
    static func amount(_ value: Int) -> String { value.formatted(.number.locale(Locale(identifier: "en_US"))) }
}

struct CuadraoChatAnswer: View {
    let turn: CanvasChatTurn
    let spanish: Bool
    let showSources: () -> Void
    let showDetails: () -> Void
    @State private var copied = false
    @State private var feedback = false
    private var es: Bool { spanish }
    private var answer: String {
        switch turn.example {
        case .savings:
            es ? "Juntarías DOP \(CanvasChatCalculation.amount(CanvasChatCalculation.total)) en seis meses, sin contar intereses."
                : "You would have DOP \(CanvasChatCalculation.amount(CanvasChatCalculation.total)) in six months, before interest."
        case .certificate:
            es ? "Empieza por tres cosas: cuánto tiempo puedes dejar ese dinero, qué rendimiento ofrece y qué pasa si lo necesitas antes."
                : "Start with three things: how long you can leave the money, the return offered, and what happens if you need it early."
        case .document:
            es ? "Podemos separar lo que aparece en el documento de lo que ya tienes registrado. Antes de añadir un movimiento, revisarías sus detalles."
                : "We can separate what appears in the document from what you have already recorded. Before adding an entry, you would review its details."
        case nil:
            es ? "Tu mensaje está en esta vista previa. Las respuestas reales se conectarán al asistente existente; aquí puedes explorar el diseño con los ejemplos."
                : "Your message is in this preview. Real replies will connect to the existing assistant; here you can explore the design with examples."
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(es ? "RESPUESTA DE EJEMPLO" : "EXAMPLE RESPONSE")
                .font(.system(size: 10, weight: .medium)).tracking(1.3).foregroundStyle(.secondary)
            Text(answer).font(.body).lineSpacing(5).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            if turn.example == .savings {
                Button(action: showDetails) {
                    VStack(alignment: .leading, spacing: 14) {
                        Text(es ? "En seis meses" : "In six months").font(.subheadline).foregroundStyle(.secondary)
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            Text("DOP").font(.subheadline).foregroundStyle(.secondary)
                            Text(CanvasChatCalculation.amount(CanvasChatCalculation.total)).font(.system(.largeTitle, design: .rounded)).monospacedDigit()
                        }
                        Divider()
                        HStack {
                            Text(es ? "Ver cálculo" : "View calculation")
                            Spacer(); Image(systemName: "chevron.right").font(.caption)
                        }.font(.subheadline)
                    }.padding(20).background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 20))
                }.buttonStyle(.plain).accessibilityIdentifier("chat-calculation")
                Text(es ? "Es una proyección; no mueve dinero ni crea una meta." : "This is a projection; it does not move money or create a goal.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            if turn.example == .certificate {
                explanation(es ? "El plazo" : "The term", es ? "Cuándo vuelve a estar disponible tu dinero." : "When your money becomes available again.")
                explanation(es ? "El rendimiento" : "The return", es ? "La tasa, cómo se calcula y cuándo se paga." : "The rate, how it is calculated, and when it is paid.")
                explanation(es ? "La salida anticipada" : "Early withdrawal", es ? "Las condiciones y posibles penalidades." : "The terms and possible penalties.")
                Button(action: showSources) {
                    Label(es ? "Sobre esta respuesta" : "About this answer", systemImage: "info.circle")
                        .font(.footnote).frame(minHeight: 44)
                }
            }
            HStack(spacing: 4) {
                Button { UIPasteboard.general.string = answer; copied = true } label: {
                    Image(systemName: copied ? "checkmark" : "doc.on.doc").frame(width: 44, height: 44)
                }.accessibilityLabel(es ? "Copiar respuesta" : "Copy response")
                Button { feedback = true } label: { Image(systemName: "hand.thumbsdown").frame(width: 44, height: 44) }
                    .accessibilityLabel(es ? "Comentar respuesta" : "Give feedback")
                Spacer()
            }.font(.system(size: 15)).foregroundStyle(.secondary)
        }
        .alert(es ? "Comentarios" : "Feedback", isPresented: $feedback) {
            Button(es ? "Listo" : "Done", role: .cancel) { }
        } message: {
            Text(es ? "Este es un ejemplo de diseño. No se envía ningún comentario." : "This is a design example. No feedback is sent.")
        }
    }
    private func explanation(_ title: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.body.weight(.semibold))
            Text(detail).font(.body).lineSpacing(4)
        }
    }
}
