import Foundation
import PencilKit

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
}
