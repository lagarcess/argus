import Foundation
import CoreGraphics

@main struct AvatarCropChecks {
    static func main() {
        var count = 0
        func check(_ condition: @autoclosure () -> Bool, _ message: String) {
            precondition(condition(), message); count += 1
        }
        for size in [CGSize(width: 1200, height: 800), CGSize(width: 800, height: 1200), CGSize(width: 512, height: 512)] {
            let geometry = CanvasAvatarCropGeometry(size: size)
            let centered = geometry.centered
            check(centered.midX == size.width / 2 && centered.midY == size.height / 2, "Fresh crop is centered")
            check(centered.width == min(size.width, size.height), "Fresh crop fills the shorter edge")
            for origin in [-10000.0, 0, 300, 10000] {
                for side in [-1.0, 1, 300, 10000] {
                    let crop = geometry.clamped(CGRect(x: origin, y: origin, width: side, height: side))
                    check(crop.width == crop.height, "Crop remains square")
                    check(crop.width >= centered.width / 4 && crop.width <= centered.width, "Zoom remains bounded")
                    check(crop.minX >= 0 && crop.minY >= 0 && crop.maxX <= size.width && crop.maxY <= size.height,
                          "Pan and zoom never expose empty margins")
                    check(geometry.clamped(crop) == crop, "Accepted crop survives reopening unchanged")
                }
            }
            check(geometry.clamped(CGRect(x: CGFloat.nan, y: 0, width: 20, height: 20)) == centered, "Invalid input resets safely")
            check(geometry.clamped(CGRect(x: 0, y: 0, width: CGFloat.infinity, height: 20)) == centered, "Infinite zoom resets safely")
            for viewport in [260.0, 340, 420] {
                let crop = geometry.clamped(CGRect(x: 90, y: 120, width: 320, height: 320))
                let scale = viewport / crop.width
                let offset = CGPoint(x: crop.minX * scale, y: crop.minY * scale)
                let restored = geometry.clamped(CGRect(x: offset.x / scale, y: offset.y / scale, width: viewport / scale, height: viewport / scale))
                check(abs(restored.minX - crop.minX) < 0.0001 && abs(restored.minY - crop.minY) < 0.0001 && abs(restored.width - crop.width) < 0.0001,
                      "Viewport resize preserves source coordinates")
            }
        }
        print("Avatar crop checks passed: \(count)")
    }
}
