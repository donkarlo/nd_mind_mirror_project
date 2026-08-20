import Foundation

struct GraphicDocumentPayload: Codable {
    var version: Int?
    var imageName: String?
    var canvasWidth: Int?
    var canvasHeight: Int?
    var drawingDataBase64: String?
    var pencil: PencilPayload?

    enum CodingKeys: String, CodingKey {
        case version
        case imageName = "image_name"
        case canvasWidth = "canvas_width"
        case canvasHeight = "canvas_height"
        case drawingDataBase64 = "drawing_data_base64"
        case pencil
    }
}

struct PencilPayload: Codable {
    var width: Double?
    var color: String?
}

struct GraphicEnvelope: Codable {
    var type: String
    var path: String?
    var operation: String?
    var message: String?
    var document: GraphicDocumentPayload?
    var pngBase64: String?
    var clientRevision: Int?

    enum CodingKeys: String, CodingKey {
        case type, path, operation, message, document
        case pngBase64 = "png_base64"
        case clientRevision = "client_revision"
    }
}
