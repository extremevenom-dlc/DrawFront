package com.drawfont.app

import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

/** Looks for a newer release on GitHub. The user installs it by tapping Download (Android asks to confirm). */
object Updater {
    const val REPO = "extremevenom-dlc/DrawFront"
    const val APK_NAME = "DrawFont-Android.apk"

    class Release(val version: String, val notes: String, val page: String, val apkUrl: String?)

    /** Latest release, or null if the repository has none yet. Call from a background thread. */
    fun fetchLatest(): Release? {
        val c = URL("https://api.github.com/repos/$REPO/releases/latest").openConnection() as HttpURLConnection
        try {
            c.connectTimeout = 8000
            c.readTimeout = 8000
            c.setRequestProperty("User-Agent", "DrawFont-updater")
            c.setRequestProperty("Accept", "application/vnd.github+json")
            val code = c.responseCode
            if (code == 404) return null
            if (code != 200) throw IOException("GitHub answered with error $code")
            val o = JSONObject(c.inputStream.bufferedReader().use { it.readText() })
            val prefix = "https://github.com/$REPO/"
            var apk: String? = null
            val assets = o.optJSONArray("assets")
            if (assets != null) {
                for (i in 0 until assets.length()) {
                    val a = assets.getJSONObject(i)
                    val url = a.optString("browser_download_url")
                    if (a.optString("name") == APK_NAME && url.startsWith(prefix)) apk = url
                }
            }
            val page = o.optString("html_url").let { if (it.startsWith(prefix)) it else "https://github.com/$REPO/releases" }
            return Release(o.optString("tag_name").trimStart('v', 'V'), o.optString("body"), page, apk)
        } finally {
            c.disconnect()
        }
    }

    private fun parts(v: String): List<Int> =
        Regex("\\d+").findAll(v.substringBefore('-')).map { it.value.toInt() }.toList()

    fun isNewer(latest: String, current: String): Boolean {
        val a = parts(latest)
        val b = parts(current)
        if (a.isEmpty() || b.isEmpty()) return false
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }
}
