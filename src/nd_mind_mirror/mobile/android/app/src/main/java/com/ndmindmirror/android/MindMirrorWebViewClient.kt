package com.ndmindmirror.android

import android.content.Intent
import android.net.Uri
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient

/**
 * Keeps the WebView on bundled application assets and delegates external links to Android.
 */
class MindMirrorWebViewClient(
    private val activity: MainActivity,
) : WebViewClient() {
    override fun shouldOverrideUrlLoading(
        view: WebView?,
        request: WebResourceRequest?,
    ): Boolean {
        val target = request?.url?.toString().orEmpty()
        if (target.startsWith(LOCAL_ASSET_ROOT)) return false
        if (target.isBlank()) return true

        runCatching {
            activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(target)))
        }
        return true
    }

    private companion object {
        const val LOCAL_ASSET_ROOT = "file:///android_asset/mobile/"
    }
}
