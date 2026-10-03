import Foundation
import CoreGraphics

struct CanvasAvatarCropGeometry {
    let size: CGSize
    var centered: CGRect {
        let side = min(size.width, size.height)
        return CGRect(x: (size.width - side) / 2, y: (size.height - side) / 2, width: side, height: side)
    }
    func clamped(_ crop: CGRect) -> CGRect {
        guard crop.origin.x.isFinite, crop.origin.y.isFinite, crop.width.isFinite, crop.height.isFinite else { return centered }
        let side = min(centered.width, max(centered.width / 4, crop.width))
        return CGRect(x: min(max(0, crop.midX - side / 2), size.width - side),
                      y: min(max(0, crop.midY - side / 2), size.height - side), width: side, height: side)
    }
}
