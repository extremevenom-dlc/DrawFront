package com.drawfont.app

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import java.io.File

object Share {
    /** Opens Android's share sheet (WhatsApp, Discord, Drive, Files...) for a file in the app's cache/share folder. */
    fun file(ctx: Context, file: File, mime: String, title: String) {
        val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".files", file)
        val send = Intent(Intent.ACTION_SEND).apply {
            type = mime
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        ctx.startActivity(Intent.createChooser(send, title))
    }

    fun shareDir(ctx: Context): File {
        val d = File(ctx.cacheDir, "share")
        d.mkdirs()
        return d
    }
}
