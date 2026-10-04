package de.bgg_home.texslate

/**
 * JNI entry point required by the bundled TeXslate/Tectonic ARM64 library.
 *
 * The package and object names intentionally match the unmodified native JNI
 * symbols exported by libtexslate_native.so.
 */
object RustBridge {
    init {
        System.loadLibrary("texslate_native")
    }

    external fun tectonicVersion(): String

    external fun tectonicCompileToFile(
        texSource: String,
        jobDir: String,
        buildEpochSeconds: Long,
        fontconfigFile: String,
        continueOnErrors: Boolean,
    ): String
}
