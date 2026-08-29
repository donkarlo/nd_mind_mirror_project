// swift-tools-version: 5.9

import PackageDescription
import AppleProductTypes

let package = Package(
    name: "ND Graphic M4",
    platforms: [
        .iOS("17.0")
    ],
    products: [
        .iOSApplication(
            name: "ND Graphic M4",
            targets: ["AppModule"],
            bundleIdentifier: "com.nd.mindmirror.graphic.m4",
            displayVersion: "4.0.0",
            bundleVersion: "400",
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
