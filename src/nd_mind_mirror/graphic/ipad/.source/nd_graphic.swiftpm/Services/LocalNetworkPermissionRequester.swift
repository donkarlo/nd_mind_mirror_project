import Foundation
import Network

/// Waits until iPadOS has actually resolved Local Network privacy before the
/// graphic transport is started.  Earlier builds optimistically continued
/// after two seconds; if the permission sheet was still on screen, the first
/// connection was already doomed with POSIX 50 / NSURLError -1009.
final class LocalNetworkPermissionRequester {
    static let shared = LocalNetworkPermissionRequester()

    private var browser: NWBrowser?
    private var completion: ((Bool, String?) -> Void)?
    private var stateUpdate: ((String) -> Void)?
    private var timeoutWorkItem: DispatchWorkItem?
    private var finished = false

    private init() {}

    func request(
        stateUpdate: @escaping (String) -> Void = { _ in },
        completion: @escaping (Bool, String?) -> Void
    ) {
        finishCleanup()
        self.completion = completion
        self.stateUpdate = stateUpdate
        self.finished = false

        let parameters = NWParameters.tcp
        parameters.includePeerToPeer = false
        let browser = NWBrowser(
            for: .bonjour(type: "_ndmindmirror._tcp", domain: "local."),
            using: parameters
        )
        self.browser = browser

        stateUpdate("Local Network authorization probe started")

        browser.stateUpdateHandler = { [weak self] state in
            guard let self else { return }
            switch state {
            case .setup:
                self.stateUpdate?("Local Network browser state=setup")
            case .ready:
                self.stateUpdate?("Local Network browser state=ready")
                self.finish(
                    allowed: true,
                    message: "Local Network permission is active"
                )
            case .waiting(let error):
                // Do not fail here. While the privacy sheet is visible iPadOS
                // can report a policy/waiting state. The same browser normally
                // becomes .ready immediately after the user taps Allow.
                self.stateUpdate?("Local Network browser state=waiting error=\(error)")
            case .failed(let error):
                self.stateUpdate?("Local Network browser state=failed error=\(error)")
                self.finish(allowed: false, message: String(describing: error))
            case .cancelled:
                self.stateUpdate?("Local Network browser state=cancelled")
            @unknown default:
                self.stateUpdate?("Local Network browser state=unknown")
            }
        }

        browser.browseResultsChangedHandler = { [weak self] results, _ in
            self?.stateUpdate?("Local Network Bonjour results=\(results.count)")
        }
        browser.start(queue: .main)

        // Give the user enough time to read and answer the system permission
        // sheet. Never treat this timeout as success.
        let timeout = DispatchWorkItem { [weak self] in
            guard let self, !self.finished else { return }
            self.stateUpdate?("Local Network authorization timed out after 45s")
            self.finish(
                allowed: false,
                message: "Timed out waiting for Local Network permission. Verify ND Graphic is enabled in Settings → Privacy & Security → Local Network, then press Connect again."
            )
        }
        timeoutWorkItem = timeout
        DispatchQueue.main.asyncAfter(deadline: .now() + 45.0, execute: timeout)
    }

    private func finish(allowed: Bool, message: String?) {
        guard !finished else { return }
        finished = true
        let callback = completion
        finishCleanup()
        callback?(allowed, message)
    }

    private func finishCleanup() {
        timeoutWorkItem?.cancel()
        timeoutWorkItem = nil
        browser?.cancel()
        browser = nil
        completion = nil
        stateUpdate = nil
    }
}
