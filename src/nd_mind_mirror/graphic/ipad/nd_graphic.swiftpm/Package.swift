// swift-tools-version: 5.9

import PackageDescription
import AppleProductTypes

let package = Package(
    name: "ND Graphic",
    platforms: [
        .iOS("17.0")
    ],
    products: [
        .iOSApplication(
            name: "ND Graphic",
            targets: ["AppModule"],
            bundleIdentifier: "com.nd.mindmirror.graphic",
            displayVersion: "0.31.41",
            bundleVersion: "71",
            appIcon: .placeholder(icon: .pencil),
            accentColor: .presetColor(.blue),
            supportedDeviceFamilies: [
                .pad
            ],
            supportedInterfaceOrientations: [
                .landscapeRight,
                .landscapeLeft,
                .portrait,
                .portraitUpsideDown(.when(deviceFamilies: [.pad]))
            ],
            additionalInfoPlistContentFilePath: "Info.plist"
        )
    ],
    targets: [
        .executableTarget(
            name: "AppModule",
            path: "."
        )
    ]
)
