package com.ndmindmirror.android.latex.compiler

import java.io.File

/**
 * Result of one local Tectonic compilation.
 */
data class LatexCompileResult(
    val ok: Boolean,
    val sourcePath: String,
    val pdfFile: File?,
    val log: String,
    val error: String,
    val exportedPath: String? = null,
)
