import SwiftUI
import PhotosUI

enum CanvasProfileAvatarStyle: Equatable {
    case initial
    case theme(CanvasPlanLook)
    case photo(CanvasAvatarPhoto)
}

struct CanvasProfileAvatar: View {
    let name: String
    let style: CanvasProfileAvatarStyle
    var size: CGFloat = 64

    var body: some View {
        Group {
            switch style {
            case .initial:
                Text(String(name.trimmingCharacters(in: .whitespacesAndNewlines).prefix(1)).uppercased())
                    .frame(width: size, height: size)
                    .foregroundStyle(WelcomePalette.pine).background(WelcomePalette.sage)
            case .theme(let theme):
                Image(systemName: theme.symbol).frame(width: size, height: size)
                    .foregroundStyle(theme.color).background(theme.color.opacity(0.12))
            case .photo(let photo):
                if let image = UIImage(data: photo.thumbnail) {
                    Image(uiImage: image).resizable().scaledToFill().frame(width: size, height: size)
                }
            }
        }.font(.system(.title, design: .rounded, weight: .medium))
            .frame(width: size, height: size).clipShape(Circle()).accessibilityHidden(true)
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
    @State private var cropRequest: CanvasAvatarCropRequest?

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
            if case .photo(let photo) = avatar {
                Button(spanish ? "Ajustar foto" : "Reposition photo") {
                    cropRequest = CanvasAvatarCropRequest(source: photo.source, crop: photo.crop)
                }.accessibilityIdentifier("cuadrao.profile.photo.edit")
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
                    guard let source = try await selectedPhoto.loadTransferable(type: CanvasAvatarSource.self) else {
                        throw CanvasAvatarPhotoError.unreadable
                    }
                    guard !Task.isCancelled, generation == request else { return }
                    cropRequest = CanvasAvatarCropRequest(source: source, crop: source.centeredCrop)
                    loading = false; self.selectedPhoto = nil
                } catch {
                    guard !Task.isCancelled, generation == request else { return }
                    loading = false; loadFailed = true; self.selectedPhoto = nil
                }
            }
            .sheet(item: $cropRequest) { request in
                CanvasAvatarCropSheet(request: request, spanish: spanish) { avatar = .photo($0) }
            }
            .onDisappear { generation = UUID(); selectedPhoto = nil; loading = false }
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
