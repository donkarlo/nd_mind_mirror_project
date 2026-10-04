import Combine
import Foundation

/// Persists Pencil contact-preview timing preferences.
@MainActor
final class PencilContactPreviewSettingsStore: ObservableObject {
    static let minimumIdleSeconds = 1.0
    static let maximumIdleSeconds = 10.0
    static let idleStepSeconds = 0.5
    static let defaultIdleSeconds = 2.0

    @Published private(set) var minimumIdleSeconds: Double

    private enum Keys {
        static let minimumIdleSeconds = "graphic.pencil_contact_preview.minimum_idle_seconds"
    }

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if defaults.object(forKey: Keys.minimumIdleSeconds) == nil {
            minimumIdleSeconds = Self.defaultIdleSeconds
        } else {
            minimumIdleSeconds = Self.clamped(
                defaults.double(forKey: Keys.minimumIdleSeconds)
            )
        }
    }

    func save(minimumIdleSeconds: Double) {
        let value = Self.clamped(minimumIdleSeconds)
        self.minimumIdleSeconds = value
        defaults.set(value, forKey: Keys.minimumIdleSeconds)
    }

    private static func clamped(_ value: Double) -> Double {
        min(max(value, minimumIdleSeconds), maximumIdleSeconds)
    }
}
