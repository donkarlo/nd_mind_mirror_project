package com.ndmindmirror.android.latex.compiler

import android.webkit.WebView
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

/**
 * Runs blocking Tectonic work away from the WebView thread and returns results
 * through a request-id callback.
 */
class AndroidLatexCompileCoordinator(
    private val webView: WebView,
    private val compileService: LatexCompileService,
) {
    private val executor = Executors.newSingleThreadExecutor()
    private val latestPreviewRequestId = AtomicInteger(0)

    fun request(
        requestId: Int,
        sourcePath: String,
        source: String,
        exportPdf: Boolean,
    ) {
        if (!exportPdf) {
            latestPreviewRequestId.set(requestId)
        }

        executor.submit {
            if (!exportPdf && requestId != latestPreviewRequestId.get()) {
                return@submit
            }

            val payload = try {
                val result = compileService.compile(
                    sourcePath = sourcePath,
                    source = source,
                    exportPdf = exportPdf,
                )
                compileResultJson(result, exportPdf)
            } catch (error: Throwable) {
                JSONObject()
                    .put("ok", false)
                    .put("exported", exportPdf)
                    .put("error", error.message ?: error.javaClass.simpleName)
                    .put("log", error.stackTraceToString().takeLast(MAX_LOG_CHARS))
            }

            if (!exportPdf && requestId != latestPreviewRequestId.get()) {
                return@submit
            }

            val encoded = JSONObject.quote(payload.toString())
            webView.post {
                webView.evaluateJavascript(
                    "window.mindMirrorNativeCompileResult && " +
                        "window.mindMirrorNativeCompileResult($requestId, $encoded);",
                    null,
                )
            }
        }
    }

    fun compilerVersion(): String {
        return compileService.compilerVersion()
    }

    fun previewInfo(sourcePath: String): JSONObject {
        return compileService.latestPreviewInfo(sourcePath)
    }

    fun previewPage(sourcePath: String, pageNumber: Int): String {
        return compileService.latestPreviewPage(sourcePath, pageNumber)
    }

    fun close() {
        executor.shutdownNow()
    }

    private fun compileResultJson(
        result: LatexCompileResult,
        exported: Boolean,
    ): JSONObject {
        val payload = JSONObject()
            .put("ok", result.ok)
            .put("exported", exported)
            .put("source_path", result.sourcePath)
            .put("error", result.error)
            .put("log", result.log.takeLast(MAX_LOG_CHARS))

        result.exportedPath?.let { payload.put("exported_path", it) }

        if (result.ok) {
            val info = compileService.latestPreviewInfo(result.sourcePath)
            payload
                .put("page_count", info.optInt("page_count", 0))
                .put("preview_available", info.optBoolean("available", false))
        }

        return payload
    }

    private companion object {
        const val MAX_LOG_CHARS = 24000
    }
}
