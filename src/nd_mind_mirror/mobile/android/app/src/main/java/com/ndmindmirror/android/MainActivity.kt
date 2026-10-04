package com.ndmindmirror.android

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.webkit.WebView
import android.widget.FrameLayout
import android.widget.ProgressBar
import android.widget.Toast
import com.ndmindmirror.android.latex.compiler.AndroidLatexCompileCoordinator
import com.ndmindmirror.android.latex.compiler.LatexCompileService

/**
 * Hosts the standalone Android Mind Mirror editor over local app assets.
 */
class MainActivity : Activity() {
    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var preferences: WorkspacePreferenceStore
    private lateinit var workspace: AndroidWorkspaceService
    private lateinit var searchIndex: SearchIndexManager
    private lateinit var searchCoordinator: AndroidSearchCoordinator
    private lateinit var latexResourceCoordinator: AndroidLatexResourceCoordinator
    private lateinit var latexCompileCoordinator: AndroidLatexCompileCoordinator

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        preferences = WorkspacePreferenceStore(this)
        workspace = AndroidWorkspaceService(this, preferences)
        val preview = PdfPreviewService(this, workspace)
        val latexResources = AndroidLatexResourceService(workspace, preview)
        val recentFiles = RecentFileStore(this, preferences)
        val latexDocumentTemplates = LatexDocumentTemplateCatalog(this)

        createContentView()
        searchIndex = SearchIndexManager(this, workspace)
        searchCoordinator = AndroidSearchCoordinator(webView, searchIndex)
        latexResourceCoordinator = AndroidLatexResourceCoordinator(webView, latexResources)
        val latexCompileService = LatexCompileService(this, workspace, preview)
        latexCompileCoordinator = AndroidLatexCompileCoordinator(webView, latexCompileService)
        webView.addJavascriptInterface(
            AndroidBridge(
                this,
                workspace,
                preview,
                recentFiles,
                latexDocumentTemplates,
                latexResourceCoordinator,
                latexCompileCoordinator,
                searchCoordinator,
            ),
            "MindMirrorAndroid",
        )
        webView.loadUrl(LOCAL_INDEX)
        searchIndex.refreshActiveRoot()
    }

    private fun createContentView() {
        val container = FrameLayout(this)
        webView = WebView(this)
        progressBar = ProgressBar(this)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = true
            allowContentAccess = false
            builtInZoomControls = true
            displayZoomControls = false
            textZoom = 100
        }
        webView.webViewClient = MindMirrorWebViewClient(this)

        container.addView(
            webView,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT,
            ),
        )
        container.addView(
            progressBar,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.CENTER,
            ),
        )
        progressBar.visibility = View.GONE
        setContentView(container)
    }

    fun chooseRootFolder(locationKey: String) {
        val location = WorkspaceLocation.fromKey(locationKey)
        val requestCode = requestCodeFor(location)
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
            addFlags(
                Intent.FLAG_GRANT_READ_URI_PERMISSION or
                    Intent.FLAG_GRANT_WRITE_URI_PERMISSION or
                    Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION or
                    Intent.FLAG_GRANT_PREFIX_URI_PERMISSION
            )
        }
        startActivityForResult(intent, requestCode)
    }

    fun activateRoot(locationKey: String): Boolean {
        val location = WorkspaceLocation.fromKey(locationKey)
        val activated = preferences.setActiveLocation(location)
        if (activated) {
            searchIndex.refreshActiveRoot()
            runOnUiThread {
                notifyRootChanged()
                Toast.makeText(
                    this,
                    displayName(location) + " workspace active.",
                    Toast.LENGTH_SHORT,
                ).show()
            }
        }
        return activated
    }

    fun workspaceMutated() {
        if (::searchIndex.isInitialized) {
            searchIndex.refreshActiveRoot()
        }
    }

    @Deprecated("Deprecated by Android API; retained for minSdk compatibility.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK) return

        val location = locationForRequestCode(requestCode) ?: return
        val uri = data?.data ?: return
        val grantedFlags = data.flags and (
            Intent.FLAG_GRANT_READ_URI_PERMISSION or
                Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )
        runCatching {
            contentResolver.takePersistableUriPermission(uri, grantedFlags)
        }

        preferences.saveRootUri(location, uri)
        searchIndex.refreshActiveRoot()
        Toast.makeText(
            this,
            displayName(location) + " root folder selected.",
            Toast.LENGTH_SHORT,
        ).show()
        notifyRootChanged()
    }

    private fun notifyRootChanged() {
        webView.evaluateJavascript(
            "window.mindMirrorNativeRootChanged && window.mindMirrorNativeRootChanged();",
            null,
        )
    }

    private fun requestCodeFor(location: WorkspaceLocation): Int {
        return when (location) {
            WorkspaceLocation.LOCAL -> REQUEST_LOCAL_ROOT_FOLDER
            WorkspaceLocation.DROPBOX -> REQUEST_DROPBOX_ROOT_FOLDER
        }
    }

    private fun locationForRequestCode(requestCode: Int): WorkspaceLocation? {
        return when (requestCode) {
            REQUEST_LOCAL_ROOT_FOLDER -> WorkspaceLocation.LOCAL
            REQUEST_DROPBOX_ROOT_FOLDER -> WorkspaceLocation.DROPBOX
            else -> null
        }
    }

    private fun displayName(location: WorkspaceLocation): String {
        return when (location) {
            WorkspaceLocation.LOCAL -> "Local"
            WorkspaceLocation.DROPBOX -> "Dropbox"
        }
    }

    override fun onDestroy() {
        if (::latexCompileCoordinator.isInitialized) {
            latexCompileCoordinator.close()
        }
        if (::latexResourceCoordinator.isInitialized) {
            latexResourceCoordinator.close()
        }
        if (::searchCoordinator.isInitialized) {
            searchCoordinator.close()
        }
        if (::searchIndex.isInitialized) {
            searchIndex.close()
        }
        webView.removeJavascriptInterface("MindMirrorAndroid")
        webView.destroy()
        super.onDestroy()
    }

    private companion object {
        const val REQUEST_LOCAL_ROOT_FOLDER = 4101
        const val REQUEST_DROPBOX_ROOT_FOLDER = 4102
        const val LOCAL_INDEX = "file:///android_asset/mobile/index.html"
    }
}
