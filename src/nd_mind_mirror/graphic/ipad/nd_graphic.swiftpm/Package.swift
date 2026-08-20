// swift-tools-version: 5.9

import PackageDescription
import AppleProductTypes

let package = Package(
    name: "ND Graphic 030",
    platforms: [
        .iOS("17.0")
    ],
    products: [
        .iOSApplication(
            name: "ND Graphic 030",
            targets: ["AppModule"],
            bundleIdentifier: "com.nd.mindmirror.graphic.v030",
            displayVersion: "0.30.0",
            bundleVersion: "30",
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
            capabilities: [
                .localNetwork(
                    purposeString: "Connect to the Mind Mirror graphic bridge running on your Ubuntu computer.",
                    bonjourServiceTypes: ["_ndmindmirror._tcp"]
                ),
                .outgoingNetworkConnections()
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
