package com.ndmindmirror.android.latex.compiler

import java.io.File

/**
 * Prepared local filesystem view used by one Tectonic compilation.
 */
data class LatexCompileWorkspace(
    val jobDirectory: File,
    val sourcePath: String,
    val transformedSource: String,
)
