// Persists adjustable iPad-to-Ubuntu live graphic synchronization preferences.

import Combine
import Foundation

@MainActor
final class LiveGraphicSyncSettingsStore: ObservableObject {
    static let minimumUpdateRateHz = 1.0
    static let maximumUpdateRateHz = 20.0
    static let defaultUpdateRateHz = 10.0

    @Published private(set) var updateRateHz: Double

    private enum Keys {
        static let updateRateHz = "graphic.live_sync.update_rate_hz"
    }

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if defaults.object(forKey: Keys.updateRateHz) == nil {
            updateRateHz = Self.defaultUpdateRateHz
        } else {
            updateRateHz = Self.clamped(defaults.double(forKey: Keys.updateRateHz))
        }
    }

    func save(updateRateHz: Double) {
        let value = Self.clamped(updateRateHz)
        self.updateRateHz = value
        defaults.set(value, forKey: Keys.updateRateHz)
    }

    private static func clamped(_ value: Double) -> Double {
        min(max(value, minimumUpdateRateHz), maximumUpdateRateHz)
    }
}
