import Foundation
import PencilKit
import UIKit

struct GraphicDocumentStore {
    static func drawing(from payload: GraphicDocumentPayload?) -> PKDrawing {
        guard let encoded = payload?.drawingDataBase64,
              !encoded.isEmpty,
              let data = Data(base64Encoded: encoded),
              let drawing = try? PKDrawing(data: data) else {
            return PKDrawing()
        }
        return drawing
    }

    static func backgroundImage(from payload: GraphicDocumentPayload?) -> UIImage? {
        guard let encoded = payload?.backgroundImageBase64,
              !encoded.isEmpty,
              let data = Data(base64Encoded: encoded) else {
            return nil
        }
        return UIImage(data: data)
    }

}
