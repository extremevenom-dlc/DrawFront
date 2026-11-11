package com.drawfont.app

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.os.Bundle
import android.text.InputFilter
import android.text.InputType
import android.text.StaticLayout
import android.text.TextPaint
import android.util.TypedValue
import android.view.Gravity
import android.view.KeyEvent
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.GridLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.io.FileOutputStream

/**
 * Type with your own font and send the result as a picture. WhatsApp, Discord and friends can't show
 * a custom font, but they show pictures, so everyone sees your handwriting.
 */
class TypeActivity : Activity() {
    private lateinit var edit: EditText
    private lateinit var tf: Typeface
    private lateinit var transparent: CheckBox

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val fontPath = intent.getStringExtra("font")
        val chars = intent.getStringArrayListExtra("chars") ?: ArrayList<String>()
        try {
            tf = Typeface.createFromFile(File(fontPath ?: ""))
        } catch (e: Exception) {
            Toast.makeText(this, "Could not load the font: " + e.message, Toast.LENGTH_LONG).show()
            finish()
            return
        }

        val root = LinearLayout(this)
        root.orientation = LinearLayout.VERTICAL
        root.setBackgroundColor(Color.WHITE)
        root.setPadding(dp(8), dp(8), dp(8), dp(8))

        val head = TextView(this)
        head.text = "Type with your font"
        head.textSize = 18f
        root.addView(head)

        edit = EditText(this)
        edit.typeface = tf
        edit.setTextSize(TypedValue.COMPLEX_UNIT_SP, 34f)
        edit.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
        edit.gravity = Gravity.TOP
        edit.hint = "Tap your symbol keys below, or type on the normal keyboard"
        // Standard QWERTY in, your own private-use letters out.
        val keys = intent.getStringArrayListExtra("keys") ?: ArrayList<String>()
        val vals = intent.getStringArrayListExtra("vals") ?: ArrayList<String>()
        val keymap = HashMap<String, String>()
        for (i in 0 until minOf(keys.size, vals.size)) keymap[keys[i]] = vals[i]
        edit.filters = arrayOf(InputFilter { source, start, end, _, _, _ ->
            val out = StringBuilder()
            var changed = false
            for (i in start until end) {
                val c = source[i].toString()
                val m = keymap[c]
                if (m != null) {
                    out.append(m)
                    changed = true
                } else {
                    out.append(c)
                }
            }
            if (changed) out.toString() else null
        })
        root.addView(edit, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(170)))

        // on-screen keys: every character you drew, shown in your own handwriting
        val grid = GridLayout(this)
        grid.columnCount = 6
        for (ch in chars) {
            val b = Button(this)
            b.text = ch
            b.typeface = tf
            b.isAllCaps = false
            b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f)
            b.minWidth = 0
            b.minimumWidth = 0
            b.setOnClickListener { insert(ch) }
            val lp = GridLayout.LayoutParams()
            lp.width = dp(54)
            lp.height = dp(54)
            lp.setMargins(dp(2), dp(2), dp(2), dp(2))
            grid.addView(b, lp)
        }
        val scroll = ScrollView(this)
        scroll.addView(grid)
        root.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        val row = LinearLayout(this)
        row.orientation = LinearLayout.HORIZONTAL
        row.addView(small("Space") { insert(" ") }, weighted())
        row.addView(small("⌫") { backspace() }, weighted())
        row.addView(small("↵") { insert("\n") }, weighted())
        row.addView(small("Clear") { edit.setText("") }, weighted())
        root.addView(row)

        transparent = CheckBox(this)
        transparent.text = "Transparent background"
        root.addView(transparent)
        root.addView(small("Share as picture") { sharePicture() },
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        setContentView(root)
    }

    private fun weighted() = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)

    private fun small(text: String, onClick: () -> Unit): Button {
        val b = Button(this)
        b.text = text
        b.isAllCaps = false
        b.setOnClickListener { onClick() }
        return b
    }

    private fun insert(s: String) {
        val a = edit.selectionStart.coerceAtLeast(0)
        val b = edit.selectionEnd.coerceAtLeast(0)
        edit.text.replace(minOf(a, b), maxOf(a, b), s)
    }

    private fun backspace() {
        edit.dispatchKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DEL))
        edit.dispatchKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DEL))
    }

    private fun sharePicture() {
        val text = edit.text.toString()
        if (text.isBlank()) {
            Toast.makeText(this, "Type something first.", Toast.LENGTH_SHORT).show()
            return
        }
        val pad = 60
        val width = 1400
        val paint = TextPaint(Paint.ANTI_ALIAS_FLAG)
        paint.typeface = tf
        paint.textSize = 200f
        paint.color = Color.BLACK
        val layout = StaticLayout.Builder.obtain(text, 0, text.length, paint, width - 2 * pad)
            .setLineSpacing(0f, 1.1f)
            .build()
        if (layout.height > 8000) {
            Toast.makeText(this, "That is too long for one picture.", Toast.LENGTH_LONG).show()
            return
        }
        val bmp = Bitmap.createBitmap(width, layout.height + 2 * pad, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bmp)
        if (!transparent.isChecked) canvas.drawColor(Color.WHITE)
        canvas.translate(pad.toFloat(), pad.toFloat())
        layout.draw(canvas)
        val file = File(Share.shareDir(this), "text-" + System.currentTimeMillis() + ".png")
        FileOutputStream(file).use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        Share.file(this, file, "image/png", "Send picture")
    }
}
