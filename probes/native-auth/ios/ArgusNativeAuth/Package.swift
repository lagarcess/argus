// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "ArgusNativeAuth",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "ArgusNativeAuth", targets: ["ArgusNativeAuth"])],
    dependencies: [
        .package(url: "https://github.com/supabase/supabase-swift.git", exact: "2.55.2"),
    ],
    targets: [
        .target(
            name: "ArgusNativeAuth",
            dependencies: [.product(name: "Auth", package: "supabase-swift")]
        ),
        .testTarget(
            name: "ArgusNativeAuthTests",
            dependencies: ["ArgusNativeAuth", .product(name: "Auth", package: "supabase-swift")],
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
    ]
)
