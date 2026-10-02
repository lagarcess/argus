import SwiftUI
import PhotosUI
import ImageIO
import UniformTypeIdentifiers

enum CanvasProfileAvatarStyle: Equatable {
    case initial
    case theme(CanvasPlanLook)
    case photo(Data)
}

struct CanvasProfileAvatar: View {
    let name: String
    let style: CanvasProfileAvatarStyle

    var body: some View {
        Group {
            switch style {
            case .initial:
                Text(String(name.trimmingCharacters(in: .whitespacesAndNewlines).prefix(1)).uppercased())
                    .frame(width: 64, height: 64)
                    .foregroundStyle(WelcomePalette.pine).background(WelcomePalette.sage)
            case .theme(let theme):
                Image(systemName: theme.symbol).frame(width: 64, height: 64)
                    .foregroundStyle(theme.color).background(theme.color.opacity(0.12))
            case .photo(let data):
                if let image = UIImage(data: data) {
                    Image(uiImage: image).resizable().scaledToFill().frame(width: 64, height: 64)
                }
            }
        }.font(.system(.title, design: .rounded, weight: .medium))
            .frame(width: 64, height: 64).clipShape(Circle()).accessibilityHidden(true)
    }
}

struct CuadraoProfileAvatarPicker: View {
    let name: String
    let spanish: Bool
    @Binding var avatar: CanvasProfileAvatarStyle
    @Binding var loading: Bool
    @State private var selectedPhoto: PhotosPickerItem?
    @State private var generation = UUID()
    @State private var loadFailed = false

    private var hasPhoto: Bool {
        if case .photo = avatar { return true }
        return false
    }

    var body: some View {
        Section {
            PhotosPicker(selection: $selectedPhoto, matching: .images) {
                Label(spanish ? (hasPhoto ? "Cambiar foto" : "Elegir foto") : (hasPhoto ? "Change photo" : "Choose photo"),
                      systemImage: "photo")
            }.accessibilityIdentifier("cuadrao.profile.photo.choose")
            if loading {
                ProgressView(spanish ? "Preparando foto" : "Preparing photo")
                    .accessibilityIdentifier("cuadrao.profile.photo.loading")
            }
            if hasPhoto {
                Button(spanish ? "Quitar foto" : "Remove photo", role: .destructive) { select(.initial) }
                    .accessibilityIdentifier("cuadrao.profile.photo.remove")
            }
            if loadFailed {
                Text(spanish ? "No pudimos abrir esa foto. Intenta con otra." : "We couldn’t open that photo. Try another.")
                    .font(.footnote).foregroundStyle(.secondary)
                    .accessibilityIdentifier("cuadrao.profile.photo.error")
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 76))], spacing: 12) {
                choice(nil)
                ForEach(CanvasPlanLook.allCases) { choice($0) }
            }.padding(.vertical, 8)
        } header: { Text(spanish ? "Tu foto o avatar" : "Your photo or avatar") }
          footer: { Text(spanish ? "Tu foto se queda en esta vista previa. No se sube a tu cuenta."
                : "Your photo stays in this preview. It isn’t uploaded to your account.") }
            .listRowBackground(CanvasSettingsStyle.surface)
            .task(id: selectedPhoto) {
                guard let selectedPhoto else { return }
                let request = UUID()
                generation = request; loading = true; loadFailed = false
                do {
                    guard let data = try await selectedPhoto.loadTransferable(type: Data.self) else {
                        throw AvatarPhotoError.unreadable
                    }
                    let thumbnail = try await Task.detached(priority: .userInitiated) {
                        try avatarThumbnail(data)
                    }.value
                    guard !Task.isCancelled, generation == request else { return }
                    avatar = .photo(thumbnail)
                    loading = false
                } catch {
                    guard !Task.isCancelled, generation == request else { return }
                    loading = false; loadFailed = true
                }
            }
            .onDisappear { generation = UUID(); loading = false }
    }

    private func select(_ style: CanvasProfileAvatarStyle) {
        generation = UUID(); selectedPhoto = nil; loading = false; loadFailed = false
        avatar = style
    }

    private func choice(_ theme: CanvasPlanLook?) -> some View {
        let style = theme.map(CanvasProfileAvatarStyle.theme) ?? .initial
        let title = theme?.title(spanish) ?? (spanish ? "Inicial" : "Initial")
        return Button { select(style) } label: {
            VStack(spacing: 6) {
                CanvasProfileAvatar(name: name, style: style)
                    .overlay(alignment: .bottomTrailing) {
                        if avatar == style {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(WelcomePalette.pine, WelcomePalette.background)
                        }
                    }
                Text(title).font(.caption).foregroundStyle(.primary)
            }.frame(minHeight: 88)
        }.buttonStyle(.plain).accessibilityLabel(title)
            .accessibilityAddTraits(avatar == style ? .isSelected : [])
            .accessibilityIdentifier("cuadrao.profile.avatar.\(theme?.rawValue ?? "initial")")
    }
}

private enum AvatarPhotoError: Error { case unreadable }

private nonisolated func avatarThumbnail(_ data: Data) throws -> Data {
    guard let source = CGImageSourceCreateWithData(data as CFData, [kCGImageSourceShouldCache: false] as CFDictionary),
          let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: 512,
            kCGImageSourceShouldCacheImmediately: true
          ] as CFDictionary) else { throw AvatarPhotoError.unreadable }
    guard let output = CFDataCreateMutable(kCFAllocatorDefault, 0),
          let destination = CGImageDestinationCreateWithData(output, UTType.jpeg.identifier as CFString, 1, nil) else {
        throw AvatarPhotoError.unreadable
    }
    CGImageDestinationAddImage(destination, image, [kCGImageDestinationLossyCompressionQuality: 0.86] as CFDictionary)
    guard CGImageDestinationFinalize(destination) else { throw AvatarPhotoError.unreadable }
    return output as Data
}
