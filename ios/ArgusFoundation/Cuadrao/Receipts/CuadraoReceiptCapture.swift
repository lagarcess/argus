import SwiftUI
import PhotosUI
import VisionKit
import PDFKit
import UniformTypeIdentifiers

struct ReceiptWorkspace {
    let receipts: CuadraoReceiptStore
    let groups: CuadraoGroupPreview
    let accounts: CuadraoAccountsPreview
    let chat: CuadraoChatPreview
    let capture: (ReceiptOrigin, ReceiptSourceChoice) -> Void
    let open: (UUID) -> Void
    let groupChat: (UUID) -> Void
}
private struct ReceiptWorkspaceKey: EnvironmentKey {
    static let defaultValue: ReceiptWorkspace? = nil
}
extension EnvironmentValues {
    var receiptWorkspace: ReceiptWorkspace? {
        get { self[ReceiptWorkspaceKey.self] }
        set { self[ReceiptWorkspaceKey.self] = newValue }
    }
}
enum ReceiptRoute: Identifiable {
    case capture(ReceiptOrigin, ReceiptSourceChoice), review(UUID)
    var id: String { switch self { case .capture: "capture"; case .review(let id): id.uuidString } }
}

struct CuadraoReceiptFlow: View {
    let route: ReceiptRoute
    let workspace: ReceiptWorkspace
    let spanish: Bool
    @State private var captured: UUID?
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            Group {
                if let id = reviewID {
                    CuadraoReceiptReview(id: id, workspace: workspace, spanish: spanish)
                } else if case .capture(let origin, let source) = route {
                    CuadraoReceiptCapture(origin: origin, source: source, workspace: workspace, spanish: spanish, cancel: { dismiss() }) { id in captured = id }
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(closeTitle) { dismiss() }.accessibilityIdentifier("receipt-later")
                }
            }
        }.tint(WelcomePalette.pine).presentationDragIndicator(.visible)
    }
    private var closeTitle: String {
        let confirmed = reviewID.flatMap(workspace.receipts.receipt).map { !$0.prepared } ?? false
        if reviewID == nil { return spanish ? "Cancelar" : "Cancel" }
        return confirmed ? (spanish ? "Listo" : "Done") : (spanish ? "Después" : "Later")
    }
    private var reviewID: UUID? {
        if let captured { return captured }
        if case .review(let id) = route { return id }
        return nil
    }
}

enum ReceiptSourceChoice: String, CaseIterable, Identifiable {
    case scan, photos, file, sample
    var id: String { rawValue }
    func title(_ es: Bool) -> String {
        switch self {
        case .scan: es ? "Escanear recibo" : "Scan receipt"
        case .photos: es ? "Fotos" : "Photos"
        case .file: es ? "Archivos" : "Files"
        case .sample: es ? "Probar un recibo de ejemplo" : "Try a sample receipt"
        }
    }
    var symbol: String {
        switch self { case .scan: "doc.viewfinder"; case .photos: "photo"; case .file: "folder"; case .sample: "sparkles" }
    }
}

struct ReceiptSourceActions: View {
    let spanish: Bool
    let choose: (ReceiptSourceChoice) -> Void
    var body: some View {
        ForEach(ReceiptSourceChoice.allCases) { source in
            Button(source.title(spanish), systemImage: source.symbol) { choose(source) }
                .accessibilityIdentifier("receipt-" + source.rawValue)
        }
    }
}

typealias ReceiptCapturedFiles = [(data: Data, name: String, pdf: Bool)]

struct CuadraoReceiptCapture: View {
    let origin: ReceiptOrigin
    let source: ReceiptSourceChoice
    let workspace: ReceiptWorkspace
    let spanish: Bool
    let cancel: () -> Void
    let saved: (UUID) -> Void
    @State private var picker: ReceiptSourceChoice?
    @State private var outcome: Result<ReceiptCapturedFiles, Error>?
    @State private var pending: ReceiptCapturedFiles?
    @State private var selectedSource: ReceiptSourceChoice?
    @State private var error = ""
    @State private var started = false
    @State private var captured = false
    private var group: PlanGroup? { origin.groupID.flatMap(workspace.groups.group) }
    var body: some View {
        VStack(spacing: 24) {
            if error.isEmpty {
                ProgressView(spanish ? "Abriendo recibo…" : "Opening receipt…")
            } else {
                Image(systemName: "receipt").font(.largeTitle).foregroundStyle(WelcomePalette.pine)
                Text(error).font(CuadraoTypography.supporting).accessibilityIdentifier("receipt-error")
                if let pending {
                    Button(spanish ? "Guardar de nuevo" : "Save again") { commit(pending, example: selectedSource == .sample) }
                        .accessibilityIdentifier("receipt-retry")
                } else if selectedSource != .scan || VNDocumentCameraViewController.isSupported {
                    Button(spanish ? "Intentar de nuevo" : "Try again") { begin(selectedSource ?? source) }
                        .accessibilityIdentifier("receipt-retry")
                }
                ForEach(ReceiptSourceChoice.allCases.filter { $0 != .scan }) { alternative in
                    Button(alternative.title(spanish), systemImage: alternative.symbol) { begin(alternative) }
                        .accessibilityIdentifier("receipt-" + alternative.rawValue)
                }
            }
        }.padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(WelcomePalette.background)
            .navigationTitle(spanish ? "Un recibo" : "A receipt").navigationBarTitleDisplayMode(.inline)
            .task { guard !started else { return }; started = true; begin(source) }
            .sheet(item: $picker, onDismiss: finishPicker) { choice in
                ReceiptNativePicker(source: choice, spanish: spanish) { result in outcome = result; picker = nil }
                    .interactiveDismissDisabled()
            }
    }
    private func begin(_ source: ReceiptSourceChoice) {
        error = ""; pending = nil; outcome = nil; selectedSource = source
        guard origin.groupID == nil || group != nil else { show(ReceiptError.destination); return }
        if source == .sample { sample() }
        else if source == .scan && !VNDocumentCameraViewController.isSupported {
            error = spanish ? "El escáner no está disponible aquí. Puedes elegir una foto o un archivo." : "The scanner is unavailable here. Choose a photo or file."
        } else { picker = source }
    }
    private func finishPicker() {
        guard let outcome else { cancel(); return }
        self.outcome = nil
        switch outcome {
        case .success(let files): commit(files)
        case .failure(let failure):
            if (failure as NSError).code == NSUserCancelledError { cancel() }
            else { show(failure) }
        }
    }
    private func show(_ failure: Error) {
        error = (failure as? ReceiptError)?.message(spanish) ?? (spanish ? "No pudimos guardar el recibo. Inténtalo de nuevo." : "We couldn't save the receipt. Try again.")
    }
    private func commit(_ files: ReceiptCapturedFiles, example: Bool = false) {
        guard !captured else { return }
        pending = files
        do {
            let id = try workspace.receipts.capture(files: files, currency: example ? "DOP" : nil, origin: origin, group: group, example: example, spanish: spanish)
            captured = true; pending = nil
            if let threadID = origin.threadID { workspace.chat.attachReceipt(id, to: threadID) }
            saved(id)
        } catch { show(error) }
    }
    private func sample() {
        let renderer = UIGraphicsImageRenderer(size: CGSize(width: 600, height: 790))
        let data = renderer.jpegData(withCompressionQuality: 0.85) { context in
            UIColor.white.setFill(); context.fill(CGRect(x: 0, y: 0, width: 600, height: 790))
            let sample = ReceiptSample(spanish: spanish)
            func money(_ cents: Int) -> String { CanvasMoney.format(Decimal(cents) / 100, currency: group?.currency ?? "DOP") }
            let items = sample.lines.map { "\($0.quantity) × \($0.name)\n    \(money($0.cents))" }.joined(separator: "\n")
            let text = "\(sample.merchant)\n\(spanish ? "RECIBO DE EJEMPLO" : "SAMPLE RECEIPT")\n\n\(items)\n\nSubtotal  \(money(sample.subtotal))\n\(spanish ? "Impuesto" : "Tax")  \(money(sample.taxCents))\n\(spanish ? "Servicio" : "Service")  \(money(sample.serviceCents))\n\nTOTAL  \(money(sample.total))\n\(group?.currency ?? "DOP")"
            (text as NSString).draw(in: CGRect(x: 42, y: 48, width: 520, height: 700), withAttributes: [.font: UIFont.monospacedSystemFont(ofSize: 24, weight: .regular), .foregroundColor: UIColor.black])
        }
        commit([(data, spanish ? "Recibo de ejemplo" : "Sample receipt", false)], example: true)
    }
}
