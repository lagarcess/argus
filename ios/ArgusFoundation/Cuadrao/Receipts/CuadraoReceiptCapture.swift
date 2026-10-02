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
    let capture: (ReceiptOrigin) -> Void
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
    case capture(ReceiptOrigin), review(UUID)
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
                } else if case .capture(let origin) = route {
                    CuadraoReceiptCapture(origin: origin, workspace: workspace, spanish: spanish) { id in captured = id }
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
        return confirmed ? (spanish ? "Listo" : "Done") : (spanish ? "Después" : "Later")
    }
    private var reviewID: UUID? {
        if let captured { return captured }
        if case .review(let id) = route { return id }
        return nil
    }
}

struct CuadraoReceiptCapture: View {
    let origin: ReceiptOrigin
    let workspace: ReceiptWorkspace
    let spanish: Bool
    let saved: (UUID) -> Void
    @State private var currency = "DOP"
    @State private var scanner = false
    @State private var scannedPages: [Data]?
    @State private var importer = false
    @State private var photo: PhotosPickerItem?
    @State private var error = ""
    @State private var busy = false
    @State private var captured = false
    private var group: PlanGroup? { origin.groupID.flatMap(workspace.groups.group) }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                PlanLandscape(look: .coast).frame(height: 110).clipShape(RoundedRectangle(cornerRadius: 24))
                Text(spanish ? "Guárdalo ahora.\nCuádralo después." : "Save it now.\nSplit it later.").font(CuadraoTypography.feature)
                Text(spanish ? "Revisa ahora o vuelve cuando tengas un momento." : "Review now or come back when you have a moment.")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                if let group {
                    Label(group.name + " · " + group.currency, systemImage: "lock").font(CuadraoTypography.supporting)
                } else {
                    Picker(spanish ? "Moneda del recibo" : "Receipt currency", selection: $currency) {
                        ForEach(PlanCurrency.supported, id: \.self) { Text($0).tag($0) }
                    }.accessibilityIdentifier("receipt-currency")
                }
                PlanPrimaryButton(title: spanish ? "Escanear recibo" : "Scan receipt", symbol: "doc.viewfinder") {
                    if VNDocumentCameraViewController.isSupported { scanner = true }
                    else { error = spanish ? "El escáner no está disponible aquí. Puedes elegir una foto o un archivo." : "The scanner is unavailable here. Choose a photo or file." }
                }.accessibilityIdentifier("receipt-scan")
                HStack(spacing: 24) {
                    PhotosPicker(selection: $photo, matching: .images) {
                        Label(spanish ? "Fotos" : "Photos", systemImage: "photo").frame(minHeight: 44)
                    }
                    Button { importer = true } label: { Label(spanish ? "Archivos" : "Files", systemImage: "folder").frame(minHeight: 44) }
                }
                Divider()
                Button { sample() } label: {
                    Label(spanish ? "Probar un recibo de ejemplo" : "Try a sample receipt", systemImage: "sparkles").frame(minHeight: 44)
                }.accessibilityIdentifier("receipt-sample")
                if busy { ProgressView() }
                if !error.isEmpty { Text(error).font(.subheadline).foregroundStyle(.red).accessibilityIdentifier("receipt-error") }
            }.padding(24)
        }.background(WelcomePalette.background).navigationTitle(spanish ? "Un recibo" : "A receipt").navigationBarTitleDisplayMode(.inline)
            .disabled(busy || captured)
            .sheet(isPresented: $scanner, onDismiss: {
                if let pages = scannedPages {
                    scannedPages = nil
                    commit(pages.enumerated().map { ($0.element, "\(spanish ? "Página" : "Page") \($0.offset + 1)", false) })
                }
            }) {
                ReceiptScanner { result in
                    scanner = false
                    switch result {
                    case .success(let pages): scannedPages = pages
                    case .failure(let failure): show(failure)
                    }
                }
            }
            .fileImporter(isPresented: $importer, allowedContentTypes: [.image, .pdf]) { result in
                do {
                    let url = try result.get()
                    let access = url.startAccessingSecurityScopedResource()
                    defer { if access { url.stopAccessingSecurityScopedResource() } }
                    let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
                    guard size <= 20_000_000 else { throw ReceiptError.source }
                    let data = try Data(contentsOf: url)
                    let pdf = url.pathExtension.lowercased() == "pdf"
                    if pdf {
                        guard let document = PDFDocument(data: data), (1...10).contains(document.pageCount) else { throw ReceiptError.source }
                    } else { guard UIImage(data: data) != nil else { throw ReceiptError.source } }
                    commit([(data, url.lastPathComponent, pdf)])
                } catch { show(error) }
            }
            .task(id: photo) {
                guard let photo else { return }
                busy = true
                do {
                    guard let data = try await photo.loadTransferable(type: Data.self), data.count <= 20_000_000,
                          UIImage(data: data) != nil else { throw ReceiptError.source }
                    busy = false; commit([(data, spanish ? "Foto del recibo" : "Receipt photo", false)])
                } catch { busy = false; show(error) }
            }
    }
    private func show(_ failure: Error) {
        if (failure as NSError).code == NSUserCancelledError { return }
        error = (failure as? ReceiptError)?.message(spanish) ?? (spanish ? "No pudimos guardar el recibo. Inténtalo de nuevo." : "We couldn't save the receipt. Try again.")
    }
    private func commit(_ files: [(Data, String, Bool)], example: Bool = false) {
        guard !captured else { return }
        do {
            let id = try workspace.receipts.capture(files: files, currency: currency, origin: origin, group: group, example: example, spanish: spanish)
            captured = true
            if let threadID = origin.threadID { workspace.chat.attachReceipt(id, to: threadID) }
            saved(id)
        } catch { show(error) }
    }
    private func sample() {
        let renderer = UIGraphicsImageRenderer(size: CGSize(width: 600, height: 790))
        let data = renderer.jpegData(withCompressionQuality: 0.85) { context in
            UIColor.white.setFill(); context.fill(CGRect(x: 0, y: 0, width: 600, height: 790))
            let sample = ReceiptSample(spanish: spanish)
            func money(_ cents: Int) -> String { CanvasMoney.format(Decimal(cents) / 100, currency: group?.currency ?? currency) }
            let items = sample.lines.map { "\($0.quantity) × \($0.name)\n    \(money($0.cents))" }.joined(separator: "\n")
            let text = "\(sample.merchant)\n\(spanish ? "RECIBO DE EJEMPLO" : "SAMPLE RECEIPT")\n\n\(items)\n\nSubtotal  \(money(sample.subtotal))\n\(spanish ? "Impuesto" : "Tax")  \(money(sample.taxCents))\n\(spanish ? "Servicio" : "Service")  \(money(sample.serviceCents))\n\nTOTAL  \(money(sample.total))\n\(group?.currency ?? currency)"
            (text as NSString).draw(in: CGRect(x: 42, y: 48, width: 520, height: 700), withAttributes: [.font: UIFont.monospacedSystemFont(ofSize: 24, weight: .regular), .foregroundColor: UIColor.black])
        }
        commit([(data, spanish ? "Recibo de ejemplo" : "Sample receipt", false)], example: true)
    }
}

private struct ReceiptScanner: UIViewControllerRepresentable {
    let completed: (Result<[Data], Error>) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(completed) }
    func makeUIViewController(context: Context) -> VNDocumentCameraViewController {
        let controller = VNDocumentCameraViewController(); controller.delegate = context.coordinator; return controller
    }
    func updateUIViewController(_ controller: VNDocumentCameraViewController, context: Context) {}
    final class Coordinator: NSObject, VNDocumentCameraViewControllerDelegate {
        let completed: (Result<[Data], Error>) -> Void
        private var finished = false
        init(_ completed: @escaping (Result<[Data], Error>) -> Void) { self.completed = completed }
        private func finish(_ result: Result<[Data], Error>) { guard !finished else { return }; finished = true; completed(result) }
        func documentCameraViewControllerDidCancel(_ controller: VNDocumentCameraViewController) {
            finish(.failure(NSError(domain: NSCocoaErrorDomain, code: NSUserCancelledError)))
        }
        func documentCameraViewController(_ controller: VNDocumentCameraViewController, didFailWithError error: Error) { finish(.failure(error)) }
        func documentCameraViewController(_ controller: VNDocumentCameraViewController, didFinishWith scan: VNDocumentCameraScan) {
            guard (1...10).contains(scan.pageCount) else { finish(.failure(ReceiptError.source)); return }
            let pages = (0..<scan.pageCount).compactMap { scan.imageOfPage(at: $0).jpegData(compressionQuality: 0.8) }
            guard pages.count == scan.pageCount, pages.reduce(0, { $0 + $1.count }) <= 20_000_000 else { finish(.failure(ReceiptError.source)); return }
            finish(.success(pages))
        }
    }
}
