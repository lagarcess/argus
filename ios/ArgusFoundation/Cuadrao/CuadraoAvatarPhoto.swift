import CoreTransferable
import ImageIO
import UIKit
import UniformTypeIdentifiers

struct CanvasAvatarSource: Equatable, Sendable, Transferable {
    let jpeg: Data
    let width: Int
    let height: Int
    var size: CGSize { CGSize(width: width, height: height) }
    var geometry: CanvasAvatarCropGeometry { CanvasAvatarCropGeometry(size: size) }

    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(importedContentType: .image) { received in
            try prepare(url: received.file)
        }
    }

    nonisolated static func prepare(url: URL) throws -> Self {
        try Task.checkCancellation()
        guard let source = CGImageSourceCreateWithURL(url as CFURL, [kCGImageSourceShouldCache: false] as CFDictionary),
              let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceThumbnailMaxPixelSize: 1536,
                kCGImageSourceShouldCacheImmediately: true
              ] as CFDictionary) else { throw CanvasAvatarPhotoError.unreadable }
        try Task.checkCancellation()
        return Self(jpeg: try encodeAvatarJPEG(image, limit: 1_048_576), width: image.width, height: image.height)
    }


}

struct CanvasAvatarPhoto: Equatable, Sendable {
    let source: CanvasAvatarSource
    let crop: CGRect
    let thumbnail: Data

    nonisolated init(source: CanvasAvatarSource, crop: CGRect) throws {
        try Task.checkCancellation()
        let accepted = source.geometry.clamped(crop)
        guard let image = UIImage(data: source.jpeg) else { throw CanvasAvatarPhotoError.unreadable }
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1; format.opaque = true
        let ratio = 512 / accepted.width
        let thumbnail = UIGraphicsImageRenderer(size: CGSize(width: 512, height: 512), format: format).image { context in
            UIColor.white.setFill(); context.fill(CGRect(x: 0, y: 0, width: 512, height: 512))
            image.draw(in: CGRect(x: -accepted.minX * ratio, y: -accepted.minY * ratio,
                                  width: CGFloat(source.width) * ratio, height: CGFloat(source.height) * ratio))
        }
        try Task.checkCancellation()
        guard let pixels = thumbnail.cgImage else { throw CanvasAvatarPhotoError.unreadable }
        self.source = source; self.crop = accepted
        self.thumbnail = try encodeAvatarJPEG(pixels, limit: 262_144)
    }
}

enum CanvasAvatarPhotoError: Error { case unreadable }

private nonisolated func encodeAvatarJPEG(_ image: CGImage, limit: Int) throws -> Data {
    for quality in [0.86, 0.72, 0.55, 0.35] {
        guard let output = CFDataCreateMutable(kCFAllocatorDefault, 0),
              let destination = CGImageDestinationCreateWithData(output, UTType.jpeg.identifier as CFString, 1, nil) else {
            throw CanvasAvatarPhotoError.unreadable
        }
        CGImageDestinationAddImage(destination, image, [kCGImageDestinationLossyCompressionQuality: quality] as CFDictionary)
        if CGImageDestinationFinalize(destination), CFDataGetLength(output) <= limit { return output as Data }
    }
    throw CanvasAvatarPhotoError.unreadable
}
