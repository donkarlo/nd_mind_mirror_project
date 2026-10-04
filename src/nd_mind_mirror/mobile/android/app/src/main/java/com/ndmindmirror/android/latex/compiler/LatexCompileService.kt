package com.ndmindmirror.android.latex.compiler

import android.content.Context
import com.ndmindmirror.android.AndroidWorkspaceService
import com.ndmindmirror.android.PdfPreviewService
import org.json.JSONObject
import java.io.File
import java.util.TimeZone

/**
 * Owns the persistent on-device Tectonic runtime and the latest compiled PDF.
 */
class LatexCompileService(
    context: Context,
    private val workspace: AndroidWorkspaceService,
    private val preview: PdfPreviewService,
) {
    private val runtimeDirectory = File(context.filesDir, "tectonic_runtime").apply { mkdirs() }
    private val workspaceBuilder = LatexCompileWorkspaceBuilder(
        workspace = workspace,
        runtimeDirectory = runtimeDirectory,
    )
    private val latestPreviewFile = File(runtimeDirectory, "mind_mirror_preview.pdf")

    @Volatile
    private var latestSourcePath: String? = null

    fun compilerVersion(): String {
        return TectonicNativeBridge.version()
    }

    fun compile(
        sourcePath: String,
        source: String,
        exportPdf: Boolean,
    ): LatexCompileResult {
        val prepared = workspaceBuilder.prepare(sourcePath, source)

        val rawResult = TectonicNativeBridge.compileToFile(
            prepared.transformedSource,
            prepared.jobDirectory.absolutePath,
            localBuildEpochSeconds(),
            true,
        )
        val native = JSONObject(rawResult)
        val log = native.optString("log", "")
        val nativeError = native.optString("error", "")

        if (!native.optBoolean("ok", false)) {
            return LatexCompileResult(
                ok = false,
                sourcePath = sourcePath,
                pdfFile = null,
                log = log,
                error = nativeError.ifBlank { "Tectonic compilation failed." },
            )
        }

        val generated = File(native.optString("pdfPath", ""))
        if (!generated.isFile) {
            return LatexCompileResult(
                ok = false,
                sourcePath = sourcePath,
                pdfFile = null,
                log = log,
                error = "Tectonic reported success but did not create a PDF.",
            )
        }

        publishPreview(generated)
        latestSourcePath = sourcePath

        val exportedPath = if (exportPdf) {
            val target = companionPdfPath(sourcePath)
            workspace.writeFile(target, latestPreviewFile, "application/pdf")
            target
        } else {
            null
        }

        return LatexCompileResult(
            ok = true,
            sourcePath = sourcePath,
            pdfFile = latestPreviewFile,
            log = log,
            error = "",
            exportedPath = exportedPath,
        )
    }

    fun latestPreviewInfo(sourcePath: String): JSONObject {
        val matchesSource = sourcePath == latestSourcePath && latestPreviewFile.isFile
        if (!matchesSource) {
            return JSONObject()
                .put("available", false)
                .put("compiled", true)
        }
        return preview.infoForLocalFile(latestPreviewFile)
            .put("compiled", true)
            .put("source_path", sourcePath)
    }

    fun latestPreviewPage(sourcePath: String, pageNumber: Int): String {
        require(
            sourcePath == latestSourcePath && latestPreviewFile.isFile
        ) {
            "No compiled preview is available for this source file."
        }
        return preview.pageDataUrlForLocalFile(latestPreviewFile, pageNumber)
    }

    private fun publishPreview(generated: File) {
        val temporary = File(runtimeDirectory, "mind_mirror_preview.tmp.pdf")
        generated.inputStream().use { input ->
            temporary.outputStream().use { output ->
                input.copyTo(output)
            }
        }

        if (latestPreviewFile.exists() && !latestPreviewFile.delete()) {
            temporary.delete()
            throw IllegalStateException("Could not replace the previous compiled preview.")
        }

        if (!temporary.renameTo(latestPreviewFile)) {
            temporary.inputStream().use { input ->
                latestPreviewFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            }
            temporary.delete()
        }
    }

    private fun companionPdfPath(sourcePath: String): String {
        val dot = sourcePath.lastIndexOf('.')
        return if (dot >= 0) {
            sourcePath.substring(0, dot) + ".pdf"
        } else {
            "$sourcePath.pdf"
        }
    }

    private fun localBuildEpochSeconds(): Long {
        val now = System.currentTimeMillis()
        val localOffset = TimeZone.getDefault().getOffset(now)
        return (now + localOffset) / 1000L
    }
}
