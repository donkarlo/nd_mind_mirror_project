import PencilKit
import UIKit
import Vision

struct HandwritingRecognition {
    let text: String
    let canvasBounds: CGRect

    var center: CGPoint {
        CGPoint(x: canvasBounds.midX, y: canvasBounds.midY)
    }
}

enum HandwritingRecognitionError: LocalizedError {
    case emptyDrawing
    case couldNotRender
    case noTextRecognized

    var errorDescription: String? {
        switch self {
        case .emptyDrawing:
            return "No handwriting was captured."
        case .couldNotRender:
            return "The handwriting could not be prepared for recognition."
        case .noTextRecognized:
            return "No text was recognized. Try writing a little larger or more clearly."
        }
    }
}

enum HandwritingRecognizer {
    /// Recognizes one handwriting phrase collected from Apple Pencil strokes.
    ///
    /// Pencil strokes are kept as vector data until this point. They are rendered
    /// to a tight high-resolution image only for Apple's Vision text recognizer.
    static func recognize(strokes: [PKStroke]) throws -> HandwritingRecognition {
        guard !strokes.isEmpty else {
            throw HandwritingRecognitionError.emptyDrawing
        }

        let drawing = PKDrawing(strokes: strokes)
        var bounds = drawing.bounds
        guard !bounds.isNull, !bounds.isEmpty else {
            throw HandwritingRecognitionError.emptyDrawing
        }

        // Give glyph ascenders/descenders and dots some breathing room.
        bounds = bounds.insetBy(dx: -18, dy: -18)
        let inkImage = drawing.image(from: bounds, scale: 3.0)

        let renderer = UIGraphicsImageRenderer(size: inkImage.size)
        let whiteBackgroundImage = renderer.image { context in
            UIColor.white.setFill()
            context.fill(CGRect(origin: .zero, size: inkImage.size))
            inkImage.draw(at: .zero)
        }

        guard let cgImage = whiteBackgroundImage.cgImage else {
            throw HandwritingRecognitionError.couldNotRender
        }

        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        request.automaticallyDetectsLanguage = true
        request.minimumTextHeight = 0.015

        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        try handler.perform([request])

        let lines = (request.results ?? []).compactMap { observation in
            observation.topCandidates(1).first?.string
        }
        let text = lines
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        guard !text.isEmpty else {
            throw HandwritingRecognitionError.noTextRecognized
        }

        return HandwritingRecognition(text: text, canvasBounds: drawing.bounds)
    }
}
