package com.ndmindmirror.android

import android.webkit.JavascriptInterface
import com.ndmindmirror.android.latex.compiler.AndroidLatexCompileCoordinator
import org.json.JSONArray
import org.json.JSONObject

/**
 * Exposes local Android workspace operations to the bundled Mind Mirror web UI.
 */
class AndroidBridge(
    private val activity: MainActivity,
    private val workspace: AndroidWorkspaceService,
    private val preview: PdfPreviewService,
    private val recentFiles: RecentFileStore,
    private val latexDocumentTemplates: LatexDocumentTemplateCatalog,
    private val latexResources: AndroidLatexResourceCoordinator,
    private val latexCompile: AndroidLatexCompileCoordinator,
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
    fun createFile(directoryPath: String, fileName: String): String = result {
        val created = workspace.createTextFile(
            directoryPath = directoryPath,
            fileName = fileName,
            content = "",
        )
        activity.workspaceMutated()
        created
    }

    @JavascriptInterface
    fun createFolder(directoryPath: String, folderName: String): String = result {
        val created = workspace.createDirectory(
            directoryPath = directoryPath,
            folderName = folderName,
        )
        activity.workspaceMutated()
        created
    }

    @JavascriptInterface
    fun latexTemplates(): String = result {
        JSONObject().put("templates", latexDocumentTemplates.items())
    }

    @JavascriptInterface
    fun createLatexFile(
        directoryPath: String,
        fileName: String,
        templateId: String,
    ): String = result {
        val candidate = fileName.trim()
        val normalizedName = if (candidate.substringAfterLast('/', candidate).contains('.')) {
            candidate
        } else {
            "$candidate.tex"
        }
        val created = workspace.createTextFile(
            directoryPath = directoryPath,
            fileName = normalizedName,
            content = latexDocumentTemplates.content(templateId),
            mimeType = "text/x-tex",
        )
        activity.workspaceMutated()
        created
    }

    @JavascriptInterface
    fun rememberRecentFile(path: String) {
        recentFiles.remember(path)
    }

    @JavascriptInterface
    fun recentFiles(): String = result {
        val validPaths = recentFiles.paths()
            .filter { path -> workspace.fileExists(path) }
            .take(MAX_RECENT_FILES)
        recentFiles.replace(validPaths)

        val values = JSONArray()
        validPaths.forEach { path ->
            values.put(
                JSONObject()
                    .put("path", path)
                    .put("name", path.substringAfterLast('/'))
            )
        }
        JSONObject().put("files", values)
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
    fun requestLatexCompile(
        requestId: Int,
        path: String,
        source: String,
        exportPdf: Boolean,
    ) {
        latexCompile.request(requestId, path, source, exportPdf)
    }

    @JavascriptInterface
    fun compiledPreviewInfo(path: String): String = result {
        latexCompile.previewInfo(path)
    }

    @JavascriptInterface
    fun compiledPreviewPage(path: String, pageNumber: Int): String = result {
        JSONObject().put(
            "data_url",
            latexCompile.previewPage(path, pageNumber),
        )
    }

    @JavascriptInterface
    fun compilerInfo(): String = result {
        JSONObject().put("version", latexCompile.compilerVersion())
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

    private companion object {
        const val MAX_RECENT_FILES = 30
    }
}
