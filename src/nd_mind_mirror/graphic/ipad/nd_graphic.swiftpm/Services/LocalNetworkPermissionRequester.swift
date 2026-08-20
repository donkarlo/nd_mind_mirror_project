import Foundation
import Network

/// Triggers iPadOS local-network privacy authorization before the WebSocket is opened.
/// Direct URLSession access can otherwise fail with NSURLErrorDomain -1009
/// ("Local network prohibited") without showing a useful prompt on some iPadOS versions.
final class LocalNetworkPermissionRequester {
    static let shared = LocalNetworkPermissionRequester()

    private var browser: NWBrowser?
    private var completion: ((Bool, String?) -> Void)?
    private var finished = false

    private init() {}

    func request(completion: @escaping (Bool, String?) -> Void) {
        finishCleanup()
        self.completion = completion
        self.finished = false

        let parameters = NWParameters.tcp
        parameters.includePeerToPeer = false
        let browser = NWBrowser(
            for: .bonjour(type: "_ndmindmirror._tcp", domain: "local."),
            using: parameters
        )
        self.browser = browser

        browser.stateUpdateHandler = { [weak self] state in
            guard let self else { return }
            switch state {
            case .ready:
                self.finish(allowed: true, message: nil)
            case .failed(let error):
                self.finish(allowed: false, message: String(describing: error))
            case .waiting(let error):
                // Keep waiting briefly: this state is also seen while the system
                // permission sheet is being presented.
                let text = String(describing: error)
                if text.localizedCaseInsensitiveContains("PolicyDenied") {
                    self.finish(allowed: false, message: text)
                }
            default:
                break
            }
        }
        browser.start(queue: .main)

        // Browsing an empty Bonjour type may remain ready/waiting with no results.
        // After the privacy prompt has had time to appear, continue to the direct
        // connection and let it provide the authoritative result.
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { [weak self] in
            guard let self, !self.finished else { return }
            self.finish(allowed: true, message: nil)
        }
    }

    private func finish(allowed: Bool, message: String?) {
        guard !finished else { return }
        finished = true
        let callback = completion
        finishCleanup()
        callback?(allowed, message)
    }

    private func finishCleanup() {
        browser?.cancel()
        browser = nil
        completion = nil
    }
}
