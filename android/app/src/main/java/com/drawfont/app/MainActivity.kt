package com.drawfont.app

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import com.chaquo.python.Python
import java.io.File
import kotlin.concurrent.thread

class MainActivity : Activity() {
    private lateinit var project: Project
    private lateinit var draw: DrawView
    private lateinit var titleView: TextView
    private lateinit var charRow: LinearLayout
    private lateinit var charScroll: HorizontalScrollView
    private lateinit var eraserBtn: Button
    private val charButtons = mutableListOf<Button>()
    private var current = "A"

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()
    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
    private fun projectFile() = File(filesDir, "project.json")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        project = try {
            if (projectFile().exists()) Project.fromJson(projectFile().readText()) else Project()
        } catch (e: Exception) {
            Project()
        }
        current = project.charset.firstOrNull() ?: "A"

        val root = LinearLayout(this)
        root.orientation = LinearLayout.VERTICAL
        root.setBackgroundColor(Color.WHITE)

        titleView = TextView(this)
        titleView.textSize = 18f
        titleView.setPadding(dp(12), dp(10), dp(12), dp(4))
        root.addView(titleView)

        charScroll = HorizontalScrollView(this)
        charRow = LinearLayout(this)
        charRow.orientation = LinearLayout.HORIZONTAL
        charScroll.addView(charRow)
        root.addView(charScroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        draw = DrawView(this)
        draw.penWidth = project.pen
        draw.onBeforeEdit = { project.snapshot(current) }
        draw.onEdited = {
            save()
            refreshCharButtons()
            updateTitle()
        }
        root.addView(draw, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        root.addView(slider("Pen thickness", 10, 140, project.pen.toInt()) { v ->
            project.pen = v.toFloat()
            draw.penWidth = v.toFloat()
        })
        root.addView(slider("Letter gap", 0, 150, project.sidebearing) { v -> project.sidebearing = v })

        val alias = CheckBox(this)
        alias.text = "Also make normal keys show my letters"
        alias.isChecked = project.latinAliases
        alias.setPadding(dp(12), 0, dp(12), 0)
        alias.setOnCheckedChangeListener { _, checked ->
            project.latinAliases = checked
            save()
        }
        root.addView(alias)

        val row1 = LinearLayout(this)
        row1.orientation = LinearLayout.HORIZONTAL
        row1.addView(button("Undo") { undo() }, weighted())
        row1.addView(button("Clear") {
            project.clear(current)
            afterReplace()
        }, weighted())
        eraserBtn = button("Pen") { toggleEraser() }
        row1.addView(eraserBtn, weighted())
        row1.addView(button("+ Symbol") { newSymbolDialog() }, weighted())
        root.addView(row1)

        val row2 = LinearLayout(this)
        row2.orientation = LinearLayout.HORIZONTAL
        row2.addView(button("Export font") { exportFont() }, weighted())
        row2.addView(button("Type & share") { openTypeScreen() }, weighted())
        row2.addView(button("Updates") { checkForUpdate(true) }, weighted())
        root.addView(row2)

        val row3 = LinearLayout(this)
        row3.orientation = LinearLayout.HORIZONTAL
        row3.addView(button("Import font / project") { importFile() }, weighted())
        root.addView(row3)

        setContentView(root)
        buildCharBar()
        select(current)
        checkForUpdate(false)
    }

    override fun onPause() {
        super.onPause()
        save()
    }

    // ---- small UI helpers
    private fun weighted() = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)

    private fun button(text: String, onClick: () -> Unit): Button {
        val b = Button(this)
        b.text = text
        b.isAllCaps = false
        b.setOnClickListener { onClick() }
        return b
    }

    private fun slider(label: String, min: Int, max: Int, start: Int, onChange: (Int) -> Unit): View {
        val box = LinearLayout(this)
        box.orientation = LinearLayout.HORIZONTAL
        box.setPadding(dp(12), 0, dp(12), 0)
        val tv = TextView(this)
        tv.text = label
        box.addView(tv, LinearLayout.LayoutParams(dp(110), ViewGroup.LayoutParams.WRAP_CONTENT))
        val sb = SeekBar(this)
        sb.max = max - min
        sb.progress = (start - min).coerceIn(0, max - min)
        sb.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                if (fromUser) {
                    onChange(progress + min)
                    save()
                }
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })
        box.addView(sb, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        return box
    }

    // ---- character list
    private fun buildCharBar() {
        charRow.removeAllViews()
        charButtons.clear()
        for (ch in project.charset) {
            val b = Button(this)
            b.isAllCaps = false
            b.minWidth = 0
            b.minimumWidth = dp(46)
            b.setOnClickListener { select(ch) }
            charButtons.add(b)
            charRow.addView(b, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(46)))
        }
        refreshCharButtons()
    }

    private fun refreshCharButtons() {
        project.charset.forEachIndexed { i, ch ->
            if (i < charButtons.size) {
                val b = charButtons[i]
                val drawn = project.isDrawn(ch)
                b.text = project.display(ch) + (if (drawn) " •" else "")
                b.setBackgroundColor(if (ch == current) 0xFF2B2D42.toInt() else if (drawn) 0xFFD6E4FF.toInt() else 0xFFEEEEEE.toInt())
                b.setTextColor(if (ch == current) Color.WHITE else Color.BLACK)
            }
        }
    }

    private fun select(ch: String) {
        current = ch
        draw.strokes = project.strokes(ch)
        draw.hint = project.display(ch)
        draw.invalidate()
        refreshCharButtons()
        updateTitle()
    }

    private fun updateTitle() {
        titleView.text = "Draw: " + project.display(current) + "     (" + project.drawnChars().size + " drawn)"
    }

    /** After the project replaced a character's stroke list (undo / clear), re-point the pad at it. */
    private fun afterReplace() {
        draw.strokes = project.strokes(current)
        draw.invalidate()
        save()
        refreshCharButtons()
        updateTitle()
    }

    private fun undo() {
        val ch = project.undo() ?: return
        if (ch != current) select(ch)
        afterReplace()
    }

    private fun toggleEraser() {
        draw.eraser = !draw.eraser
        eraserBtn.text = if (draw.eraser) "Eraser" else "Pen"
    }

    private fun newSymbolDialog() {
        val box = LinearLayout(this)
        box.orientation = LinearLayout.VERTICAL
        box.setPadding(dp(20), dp(8), dp(20), 0)
        val name = EditText(this)
        name.hint = "Name (for example: ka)"
        name.setSingleLine()
        val key = EditText(this)
        key.hint = "Keyboard key (optional, for example: k)"
        key.setSingleLine()
        box.addView(name)
        box.addView(key)
        AlertDialog.Builder(this)
            .setTitle("New custom symbol")
            .setView(box)
            .setPositiveButton("Add") { _, _ ->
                try {
                    val ch = project.newSymbol(name.text.toString(), key.text.toString().trim())
                    buildCharBar()
                    select(ch)
                    save()
                    charScroll.post { charScroll.fullScroll(View.FOCUS_RIGHT) }
                } catch (e: IllegalArgumentException) {
                    toast(e.message ?: "Could not add the symbol")
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    // ---- saving, font building, sharing
    private fun save() {
        try {
            projectFile().writeText(project.toJson())
        } catch (e: Exception) {
            // best effort: drawing must never crash because storage is full
        }
    }

    private fun buildFont(onDone: (File) -> Unit) {
        if (project.drawnChars().isEmpty()) {
            toast("Draw at least one character first.")
            return
        }
        val json = project.toJson()
        val safe = project.name.filter { it.isLetterOrDigit() }.ifEmpty { "MyHandwriting" }
        val out = File(Share.shareDir(this), "$safe.ttf")
        toast("Building your font…")
        thread {
            try {
                Python.getInstance().getModule("bridge").callAttr("build", json, out.absolutePath)
                runOnUiThread { onDone(out) }
            } catch (e: Exception) {
                runOnUiThread { toast("Could not build the font: " + e.message) }
            }
        }
    }

    private fun exportFont() {
        val input = EditText(this)
        input.setText(project.name)
        input.setSingleLine()
        val holder = LinearLayout(this)
        holder.setPadding(dp(20), dp(8), dp(20), 0)
        holder.addView(input, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        AlertDialog.Builder(this)
            .setTitle("Font name")
            .setView(holder)
            .setPositiveButton("Export") { _, _ ->
                project.name = input.text.toString().trim().ifEmpty { "MyHandwriting" }
                save()
                buildFont { file -> Share.file(this, file, "application/octet-stream", "Send your font") }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun openTypeScreen() {
        buildFont { file ->
            val chars = ArrayList<String>()
            val names = ArrayList<String>()
            for (ch in project.drawnChars()) {
                chars.add(ch)
                names.add(project.display(ch))
            }
            val i = Intent(this, TypeActivity::class.java)
            i.putExtra("font", file.absolutePath)
            i.putStringArrayListExtra("chars", chars)
            i.putStringArrayListExtra("names", names)
            val keys = ArrayList<String>()
            val vals = ArrayList<String>()
            for ((k, v) in project.keymap) {
                keys.add(k)
                vals.add(v)
            }
            i.putStringArrayListExtra("keys", keys)
            i.putStringArrayListExtra("vals", vals)
            startActivity(i)
        }
    }

    // ---- import a font or project made on the PC (or another phone)
    private val importRequest = 4711

    private fun importFile() {
        val pick = Intent(Intent.ACTION_OPEN_DOCUMENT)
        pick.addCategory(Intent.CATEGORY_OPENABLE)
        pick.type = "*/*"
        startActivityForResult(pick, importRequest)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val uri = data?.data
        if (requestCode != importRequest || resultCode != RESULT_OK || uri == null) return
        toast("Opening\u2026")
        thread {
            var imported: Project? = null
            var error: String? = null
            try {
                val bytes = contentResolver.openInputStream(uri)!!.use { it.readBytes() }
                val isFont = bytes.size > 4 && bytes[0].toInt() == 0 && bytes[1].toInt() == 1 &&
                    bytes[2].toInt() == 0 && bytes[3].toInt() == 0
                val json = if (isFont) {
                    val tmp = File(cacheDir, "import.ttf")
                    tmp.writeBytes(bytes)
                    Python.getInstance().getModule("bridge").callAttr("project_json_from_font", tmp.absolutePath).toString()
                } else {
                    String(bytes, Charsets.UTF_8).trimStart('\uFEFF')
                }
                imported = Project.fromJson(json)
            } catch (e: Exception) {
                error = e.message ?: "Could not open that file."
            }
            val failure = error
            val opened = imported
            runOnUiThread {
                if (failure != null) toast(failure) else if (opened != null) confirmImport(opened)
            }
        }
    }

    private fun confirmImport(p: Project) {
        AlertDialog.Builder(this)
            .setTitle("Open \u201C" + p.name + "\u201D?")
            .setMessage("This replaces what is on the pad now (" + project.drawnChars().size + " drawn) with " +
                p.drawnChars().size + " drawn characters.")
            .setPositiveButton("Replace") { _, _ ->
                project = p
                draw.penWidth = p.pen
                save()
                buildCharBar()
                select(p.charset.firstOrNull() ?: "A")
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    // ---- updates
    private fun checkForUpdate(manual: Boolean) {
        val installed = try {
            packageManager.getPackageInfo(packageName, 0).versionName ?: "0.0.0"
        } catch (e: Exception) {
            "0.0.0"
        }
        thread {
            var release: Updater.Release? = null
            var error: String? = null
            try {
                release = Updater.fetchLatest()
            } catch (e: Exception) {
                error = e.message ?: "Could not reach GitHub."
            }
            runOnUiThread {
                if (!isFinishing) showUpdateResult(release, error, installed, manual)
            }
        }
    }

    private fun showUpdateResult(release: Updater.Release?, error: String?, installed: String, manual: Boolean) {
        if (error != null) {
            if (manual) toast("Update check failed: $error")
        } else if (release == null || !Updater.isNewer(release.version, installed)) {
            if (manual) toast("You have the latest version ($installed).")
        } else {
            AlertDialog.Builder(this)
                .setTitle("Update available")
                .setMessage("DrawFont ${release.version} is available (you have $installed).\n\n" + release.notes.take(400))
                .setPositiveButton("Download") { _, _ ->
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(release.apkUrl ?: release.page)))
                }
                .setNegativeButton("Later", null)
                .show()
        }
    }
}
