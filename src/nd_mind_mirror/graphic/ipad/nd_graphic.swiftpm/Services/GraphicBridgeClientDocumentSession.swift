// Adds document-session navigation that keeps the iPad bridge listener connected.

import PencilKit

extension GraphicBridgeClient {
    /// Closes only the active graphic while preserving the Ubuntu bridge connection/listener.
    func closeCurrentDocumentKeepingListener() {
        selectedPath = nil
        currentOperation = "update"
        document = nil
        drawing = PKDrawing()
        documentToken += 1
        status = isConnected
            ? "Connected — waiting for Mind Mirror"
            : "Waiting for Ubuntu connection"
    }
}
