package com.ndmindmirror.android

import android.webkit.JavascriptInterface
import org.json.JSONObject

/**
 * Exposes local Android workspace operations to the bundled Mind Mirror web UI.
 */
class AndroidBridge(
    private val activity: MainActivity,
    private val workspace: AndroidWorkspaceService,
    private val preview: PdfPreviewService,
    private val latexResources: AndroidLatexResourceCoordinator,
    private val searchCoordinator: AndroidSearchCoordinator,
) {
    @JavascriptInterface
    fun workspaceInfo(): String = result { workspace.workspaceInfo() }

    @JavascriptInterface
    fun workspaceSettings(): String = result { workspace.workspaceSettings() }

    @JavascriptInterface
    fun chooseRootFolder(location: String) {
        activity.runOnUiThread {
            activity.chooseRootFolder(location)
        }
    }

    @JavascriptInterface
    fun activateRoot(location: String): String {
        return result {
            val activated = activity.activateRoot(location)
            JSONObject()
                .put("activated", activated)
                .put("location", location)
        }
    }

    @JavascriptInterface
    fun listDirectory(path: String): String = result {
        workspace.listDirectory(path)
    }

    @JavascriptInterface
    fun readFile(path: String): String = result {
        workspace.readText(path)
    }

    @JavascriptInterface
    fun writeFile(path: String, content: String): String = result {
        workspace.writeText(path, content)
    }

    @JavascriptInterface
    fun searchAsync(requestId: Int, query: String, kind: String) {
        searchCoordinator.search(requestId, query, kind)
    }

    @JavascriptInterface
    fun requestLatexGraphic(requestId: Int, sourcePath: String, rawPath: String) {
        latexResources.request(requestId, sourcePath, rawPath)
    }

    @JavascriptInterface
    fun previewInfo(path: String): String = result {
        preview.info(path)
    }

    @JavascriptInterface
    fun previewPage(path: String, pageNumber: Int): String = result {
        JSONObject().put("data_url", preview.pageDataUrl(path, pageNumber))
    }

    private fun result(block: () -> JSONObject): String {
        return try {
            block().put("ok", true).toString()
        } catch (error: Exception) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
    }
}
