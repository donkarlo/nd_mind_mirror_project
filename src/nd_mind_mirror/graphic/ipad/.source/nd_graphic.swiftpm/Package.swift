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
            displayVersion: "0.30.10",
            bundleVersion: "40",
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
