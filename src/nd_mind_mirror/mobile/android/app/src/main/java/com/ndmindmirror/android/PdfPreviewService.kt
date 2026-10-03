package com.ndmindmirror.android

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import android.util.Base64
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File

/**
 * Renders an existing PDF from the selected Android workspace for the Preview tab.
 */
class PdfPreviewService(
    private val context: Context,
    private val workspace: AndroidWorkspaceService,
) {
    fun info(sourcePath: String): JSONObject {
        val pdfPath = companionPdfPath(sourcePath)
        if (!workspace.fileExists(pdfPath)) {
            return JSONObject()
                .put("available", false)
                .put("pdf_path", pdfPath)
        }

        val cached = cachePdf(pdfPath)
        ParcelFileDescriptor.open(cached, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
            PdfRenderer(descriptor).use { renderer ->
                return JSONObject()
                    .put("available", true)
                    .put("pdf_path", pdfPath)
                    .put("page_count", renderer.pageCount)
            }
        }
    }

    fun pageDataUrl(sourcePath: String, pageNumber: Int): String {
        return pageDataUrlForPdfPath(companionPdfPath(sourcePath), pageNumber)
    }

    fun pageDataUrlForPdfPath(pdfPath: String, pageNumber: Int): String {
        val cached = cachePdf(pdfPath)
        ParcelFileDescriptor.open(cached, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
            PdfRenderer(descriptor).use { renderer ->
                require(pageNumber in 1..renderer.pageCount) { "Invalid PDF page." }
                renderer.openPage(pageNumber - 1).use { page ->
                    val scale = if (page.width > TARGET_WIDTH) {
                        TARGET_WIDTH.toFloat() / page.width.toFloat()
                    } else {
                        1f
                    }
                    val width = (page.width * scale).toInt().coerceAtLeast(1)
                    val height = (page.height * scale).toInt().coerceAtLeast(1)
                    val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                    Canvas(bitmap).drawColor(Color.WHITE)
                    page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                    val bytes = ByteArrayOutputStream().use { stream ->
                        bitmap.compress(Bitmap.CompressFormat.PNG, 92, stream)
                        stream.toByteArray()
                    }
                    bitmap.recycle()
                    return "data:image/png;base64," +
                        Base64.encodeToString(bytes, Base64.NO_WRAP)
                }
            }
        }
    }

    private fun companionPdfPath(sourcePath: String): String {
        if (sourcePath.endsWith(".pdf", ignoreCase = true)) return sourcePath
        val dot = sourcePath.lastIndexOf('.')
        return if (dot >= 0) sourcePath.substring(0, dot) + ".pdf" else "$sourcePath.pdf"
    }

    private fun cachePdf(relativePath: String): File {
        val directory = File(context.cacheDir, "pdf_preview").apply { mkdirs() }
        val file = File(directory, relativePath.hashCode().toUInt().toString(16) + ".pdf")
        workspace.inputStream(relativePath).use { input ->
            file.outputStream().use { output -> input.copyTo(output) }
        }
        return file
    }

    private companion object {
        const val TARGET_WIDTH = 1200
    }
}
