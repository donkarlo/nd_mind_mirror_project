package com.ndmindmirror.android

import android.app.Instrumentation
import android.os.Bundle
import com.ndmindmirror.android.latex.compiler.LatexCompileService
import kotlin.system.measureTimeMillis

class CompilerProbeInstrumentation : Instrumentation() {
    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        start()
    }

    override fun onStart() {
        val status = Bundle()
        try {
            val preferences = WorkspacePreferenceStore(targetContext)
            val workspace = AndroidWorkspaceService(targetContext, preferences)
            val preview = PdfPreviewService(targetContext, workspace)
            val compiler = LatexCompileService(targetContext, workspace, preview)

            val sourcePath =
                "nd_research_publication/src/kind/journal_2026/todo.tex"
            val source = workspace.readTextContent(sourcePath)
            var result: com.ndmindmirror.android.latex.compiler.LatexCompileResult? = null
            val elapsed = measureTimeMillis {
                result = compiler.compile(
                    sourcePath = sourcePath,
                    source = source,
                    exportPdf = false,
                )
            }
            val compiled = requireNotNull(result)

            status.putString("version", compiler.compilerVersion())
            status.putBoolean("ok", compiled.ok)
            status.putLong("elapsed_ms", elapsed)
            status.putString("error", compiled.error)
            status.putString("log_tail", compiled.log.takeLast(12000))
            status.putLong("pdf_size", compiled.pdfFile?.length() ?: 0L)

            if (compiled.ok) {
                val info = compiler.latestPreviewInfo(sourcePath)
                status.putInt("page_count", info.optInt("page_count", 0))
                val page = compiler.latestPreviewPage(sourcePath, 1)
                status.putBoolean("page_data_url", page.startsWith("data:image/png;base64,"))
            }

            sendStatus(if (compiled.ok) 0 else -1, status)
            finish(if (compiled.ok) 0 else -1, status)
        } catch (error: Throwable) {
            status.putString("error", error.stackTraceToString())
            sendStatus(-1, status)
            finish(-1, status)
        }
    }
}
