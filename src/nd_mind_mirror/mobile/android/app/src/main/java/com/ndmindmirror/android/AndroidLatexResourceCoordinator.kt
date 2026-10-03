package com.ndmindmirror.android

import android.webkit.WebView
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Resolves LaTeX graphic resources away from the WebView thread.
 */
class AndroidLatexResourceCoordinator(
    private val webView: WebView,
    private val resources: AndroidLatexResourceService,
) {
    private val executor = Executors.newFixedThreadPool(2)

    fun request(requestId: Int, sourcePath: String, rawPath: String) {
        executor.submit {
            val result = try {
                resources.graphic(sourcePath, rawPath).put("ok", true)
            } catch (error: Exception) {
                JSONObject()
                    .put("ok", false)
                    .put("available", false)
                    .put("error", error.message ?: error.javaClass.simpleName)
            }
            val encoded = JSONObject.quote(result.toString())
            webView.post {
                webView.evaluateJavascript(
                    "window.mindMirrorNativeLatexResource && " +
                        "window.mindMirrorNativeLatexResource($requestId, $encoded);",
                    null,
                )
            }
        }
    }

    fun close() {
        executor.shutdownNow()
    }
}
