package com.ndmindmirror.android

import android.webkit.WebView
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.Future

/**
 * Runs fast local-index queries off the WebView bridge thread and returns only the latest request.
 */
class AndroidSearchCoordinator(
    private val webView: WebView,
    private val searchIndex: SearchIndexManager,
) {
    private val executor = Executors.newSingleThreadExecutor()
    private var pendingSearch: Future<*>? = null

    @Synchronized
    fun search(requestId: Int, query: String, kind: String) {
        pendingSearch?.cancel(true)
        pendingSearch = executor.submit {
            val result = try {
                searchIndex.search(query, kind).put("ok", true)
            } catch (error: Exception) {
                JSONObject()
                    .put("ok", false)
                    .put("error", error.message ?: error.javaClass.simpleName)
            }

            if (Thread.currentThread().isInterrupted) return@submit
            val encodedResult = JSONObject.quote(result.toString())
            webView.post {
                webView.evaluateJavascript(
                    "window.mindMirrorNativeSearchResults && " +
                        "window.mindMirrorNativeSearchResults($requestId, $encodedResult);",
                    null,
                )
            }
        }
    }

    @Synchronized
    fun close() {
        pendingSearch?.cancel(true)
        pendingSearch = null
        executor.shutdownNow()
    }
}
