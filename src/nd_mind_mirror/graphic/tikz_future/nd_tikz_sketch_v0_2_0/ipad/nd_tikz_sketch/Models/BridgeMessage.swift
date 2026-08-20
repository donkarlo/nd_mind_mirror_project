import Foundation

struct BridgeEnvelope: Decodable {
    let type: String
    let version: String?
    let files: [String]?
    let path: String?
    let source: String?
    let previewPNGBase64: String?
    let message: String?
    let clientRevision: Int?

    enum CodingKeys: String, CodingKey {
        case type
        case version
        case files
        case path
        case source
        case previewPNGBase64 = "preview_png_base64"
        case message
        case clientRevision = "client_revision"
    }
}
