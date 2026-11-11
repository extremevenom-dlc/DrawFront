package com.drawfont.app

import org.json.JSONArray
import org.json.JSONObject

/** One pen stroke. Points are [x, y] in font units: baseline y = 0, y grows upward, 1000 units = 1 em. */
class Stroke(var w: Float, val pts: MutableList<FloatArray>)

/**
 * Everything the user drew. Saved as the same JSON the desktop app uses, so projects move
 * between phone and PC, and Python (fontcore.py) builds the font from it.
 */
class Project(pua: Boolean = true) {
    var name = "MyHandwriting"
    var pen = 50f
    var sidebearing = 40
    /** true = every character is a private-use code point typed by a standard QWERTY key. */
    var isPua = false
    /** PUA projects only: ALSO make the plain keys (a, B, 5...) show your letters in the font. */
    var latinAliases = false
    val charset = mutableListOf<String>()
    val glyphs = mutableMapOf<String, MutableList<Stroke>>()
    val labels = mutableMapOf<String, String>()
    val keymap = mutableMapOf<String, String>()
    private val undoStack = ArrayDeque<Pair<String, List<Stroke>>>()

    init {
        val base = ('A'..'Z').toList() + ('a'..'z').toList() + ('0'..'9').toList() +
            ".,!?;:'\"-_()[]{}&@#$%*+=/\\<>|~^`".toList()
        if (pua) {
            // Fixed order = same table as fontcore.py: A-Z = U+E000.., a-z = U+E01A.., 0-9 = U+E034.., punctuation = U+E03E..
            isPua = true
            base.forEachIndexed { i, key ->
                val ch = (0xE000 + i).toChar().toString()
                charset.add(ch)
                labels[ch] = key.toString()
                keymap[key.toString()] = ch
            }
        } else {
            base.forEach { charset.add(it.toString()) }
        }
    }

    fun strokes(ch: String): MutableList<Stroke> = glyphs.getOrPut(ch) { mutableListOf() }

    fun isDrawn(ch: String): Boolean = glyphs[ch]?.isNotEmpty() == true

    fun drawnChars(): List<String> = charset.filter { isDrawn(it) }

    fun display(ch: String): String = labels[ch] ?: ch

    /** Call BEFORE changing a character's strokes so Undo can bring them back. */
    fun snapshot(ch: String) {
        val copy = strokes(ch).map { s -> Stroke(s.w, s.pts.map { it.copyOf() }.toMutableList()) }
        undoStack.addLast(Pair(ch, copy))
        if (undoStack.size > 100) undoStack.removeFirst()
    }

    /** Returns the character whose strokes were restored, or null if there is nothing to undo. */
    fun undo(): String? {
        val last = undoStack.removeLastOrNull() ?: return null
        glyphs[last.first] = last.second.toMutableList()
        return last.first
    }

    fun clear(ch: String) {
        if (isDrawn(ch)) {
            snapshot(ch)
            glyphs[ch] = mutableListOf()
        }
    }

    /** Adds a brand-new character in the private-use area (U+E000...). Throws IllegalArgumentException. */
    fun newSymbol(label: String, key: String): String {
        if (key.isNotEmpty() && (key.codePointCount(0, key.length) != 1 || key.isBlank())) {
            throw IllegalArgumentException("A keyboard key must be exactly one character.")
        }
        var cp = 0xE000
        while (cp <= 0xF8FF && (charset.contains(cp.toChar().toString()) || glyphs.containsKey(cp.toChar().toString()))) cp++
        if (cp > 0xF8FF) throw IllegalArgumentException("Too many custom symbols.")
        val ch = cp.toChar().toString()
        charset.add(ch)
        labels[ch] = label.trim().ifEmpty { "Symbol ${cp - 0xE000 + 1}" }
        if (key.isNotEmpty()) {
            keymap.remove(key)
            keymap[key] = ch
        }
        return ch
    }

    fun toJson(): String {
        val g = JSONObject()
        for ((ch, list) in glyphs) {
            if (list.isEmpty()) continue
            val arr = JSONArray()
            for (s in list) {
                val pts = JSONArray()
                for (p in s.pts) pts.put(JSONArray().put(p[0].toDouble()).put(p[1].toDouble()))
                arr.put(JSONObject().put("w", s.w.toDouble()).put("pts", pts))
            }
            g.put(ch, arr)
        }
        val settings = JSONObject()
            .put("smoothing", 2).put("pen", pen.toInt()).put("sidebearing", sidebearing)
            .put("spacing", "auto").put("fixed_advance", 600).put("space_width", 300)
            .put("latin_aliases", latinAliases)
        return JSONObject()
            .put("format", "drawfont-project").put("version", 1).put("name", name)
            .put("settings", settings).put("charset", charset.joinToString(""))
            .put("glyphs", g).put("labels", JSONObject(labels as Map<*, *>))
            .put("keymap", JSONObject(keymap as Map<*, *>))
            .put("pua", isPua)
            .toString()
    }

    companion object {
        fun fromJson(text: String): Project {
            val o = JSONObject(text)
            require(o.optString("format") == "drawfont-project") { "Not a DrawFont project." }
            val p = Project(false)
            p.isPua = o.optBoolean("pua", false)
            p.name = o.optString("name", "MyHandwriting").ifEmpty { "MyHandwriting" }
            o.optJSONObject("settings")?.let {
                p.pen = it.optDouble("pen", 50.0).toFloat()
                p.sidebearing = it.optInt("sidebearing", 40)
                p.latinAliases = it.optBoolean("latin_aliases", false)
            }
            val cs = o.optString("charset", "")
            if (cs.isNotEmpty()) {
                p.charset.clear()
                var i = 0
                while (i < cs.length) {
                    val cp = cs.codePointAt(i)
                    p.charset.add(String(Character.toChars(cp)))
                    i += Character.charCount(cp)
                }
            }
            val g = o.optJSONObject("glyphs")
            if (g != null) {
                for (ch in g.keys()) {
                    val list = mutableListOf<Stroke>()
                    val arr = g.getJSONArray(ch)
                    for (i in 0 until arr.length()) {
                        val so = arr.getJSONObject(i)
                        val pa = so.getJSONArray("pts")
                        val pts = mutableListOf<FloatArray>()
                        for (j in 0 until pa.length()) {
                            val xy = pa.getJSONArray(j)
                            pts.add(floatArrayOf(xy.getDouble(0).toFloat(), xy.getDouble(1).toFloat()))
                        }
                        if (pts.isNotEmpty()) list.add(Stroke(so.getDouble("w").toFloat(), pts))
                    }
                    if (list.isNotEmpty()) {
                        p.glyphs[ch] = list
                        if (!p.charset.contains(ch)) p.charset.add(ch)
                    }
                }
            }
            o.optJSONObject("labels")?.let { l -> for (k in l.keys()) p.labels[k] = l.getString(k) }
            o.optJSONObject("keymap")?.let { l -> for (k in l.keys()) p.keymap[k] = l.getString(k) }
            return p
        }
    }
}
