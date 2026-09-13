// Codable WebSocket envelope used only by the TikZ bridge tab.

import Foundation

struct TikZBridgeEnvelope: Decodable {
    let type: String
    let files: [String]?
    let path: String?
    let source: String?
    let previewPNGBase64: String?
    let clientRevision: Int?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case type, files, path, source, message
        case previewPNGBase64 = "preview_png_base64"
        case clientRevision = "client_revision"
    }
}
