// Provides a compact UIKit-backed thickness slider with a smaller draggable thumb for iPad.

import SwiftUI
import UIKit

/// Wraps UISlider so the thickness thumb stays small while preserving normal drag behavior.
struct CompactThicknessSlider: UIViewRepresentable {
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double

    /// Creates the UIKit slider and installs a compact symbol-based thumb image.
    func makeUIView(context: Context) -> UISlider {
        let slider = UISlider(frame: .zero)
        slider.minimumValue = Float(range.lowerBound)
        slider.maximumValue = Float(range.upperBound)
        slider.value = Float(value)
        slider.isContinuous = true
        slider.addTarget(context.coordinator, action: #selector(Coordinator.valueChanged(_:)), for: .valueChanged)

        let configuration = UIImage.SymbolConfiguration(pointSize: 10, weight: .semibold)
        let thumb = UIImage(systemName: "circle.fill", withConfiguration: configuration)
        slider.setThumbImage(thumb, for: .normal)
        slider.setThumbImage(thumb, for: .highlighted)
        return slider
    }

    /// Keeps the UIKit slider synchronized with SwiftUI state after external setting changes.
    func updateUIView(_ slider: UISlider, context: Context) {
        slider.minimumValue = Float(range.lowerBound)
        slider.maximumValue = Float(range.upperBound)
        if abs(Double(slider.value) - value) > 0.0001 {
            slider.value = Float(value)
        }
    }

    /// Creates the coordinator that quantizes slider values to the requested step.
    func makeCoordinator() -> Coordinator {
        Coordinator(owner: self)
    }

    /// Bridges UISlider value changes back into the SwiftUI binding.
    final class Coordinator: NSObject {
        private var owner: CompactThicknessSlider

        /// Stores the latest representable configuration used by the UIKit target callback.
        init(owner: CompactThicknessSlider) {
            self.owner = owner
        }

        /// Rounds the raw slider value to the configured step before updating SwiftUI state.
        @objc func valueChanged(_ slider: UISlider) {
            let raw = Double(slider.value)
            let quantized = (raw / owner.step).rounded() * owner.step
            owner.value = min(max(quantized, owner.range.lowerBound), owner.range.upperBound)
        }
    }
}
