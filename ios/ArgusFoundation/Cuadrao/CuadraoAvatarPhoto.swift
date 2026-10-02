import CoreTransferable
import ImageIO
import UIKit
import UniformTypeIdentifiers

struct CanvasAvatarSource: Equatable, Sendable, Transferable {
    let jpeg: Data
    let width: Int
    let height: Int
    var size: CGSize { CGSize(width: width, height: height) }
    var centeredCrop: CGRect {
        let side = CGFloat(min(width, height))
        return CGRect(x: (CGFloat(width) - side) / 2, y: (CGFloat(height) - side) / 2, width: side, height: side)
    }

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

    func clamped(_ crop: CGRect) -> CGRect {
        guard crop.origin.x.isFinite, crop.origin.y.isFinite, crop.width.isFinite else { return centeredCrop }
        let side = min(CGFloat(min(width, height)), max(CGFloat(min(width, height)) / 4, crop.width))
        return CGRect(x: min(max(0, crop.midX - side / 2), CGFloat(width) - side),
                      y: min(max(0, crop.midY - side / 2), CGFloat(height) - side), width: side, height: side)
    }
}

struct CanvasAvatarPhoto: Equatable, Sendable {
    let source: CanvasAvatarSource
    let crop: CGRect
    let thumbnail: Data

    nonisolated init(source: CanvasAvatarSource, crop: CGRect) throws {
        let accepted = source.clamped(crop)
        guard let image = UIImage(data: source.jpeg) else { throw CanvasAvatarPhotoError.unreadable }
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1; format.opaque = true
        let ratio = 512 / accepted.width
        let thumbnail = UIGraphicsImageRenderer(size: CGSize(width: 512, height: 512), format: format).image { context in
            UIColor.white.setFill(); context.fill(CGRect(x: 0, y: 0, width: 512, height: 512))
            image.draw(in: CGRect(x: -accepted.minX * ratio, y: -accepted.minY * ratio,
                                  width: CGFloat(source.width) * ratio, height: CGFloat(source.height) * ratio))
        }
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
