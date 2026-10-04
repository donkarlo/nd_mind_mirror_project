package com.ndmindmirror.android.latex.compiler

import de.bgg_home.texslate.RustBridge

/**
 * Mind Mirror adapter around the pinned TeXslate Tectonic JNI library.
 *
 * The third-party native binary remains unmodified and exposes its original
 * de.bgg_home.texslate JNI symbols. This adapter keeps the rest of Mind Mirror
 * independent of that package-level ABI.
 */
object TectonicNativeBridge {
    fun version(): String {
        return RustBridge.tectonicVersion()
    }

    fun compileToFile(
        texSource: String,
        jobDir: String,
        buildEpochSeconds: Long,
        continueOnErrors: Boolean,
    ): String {
        return RustBridge.tectonicCompileToFile(
            texSource,
            jobDir,
            buildEpochSeconds,
            "",
            continueOnErrors,
        )
    }
}
