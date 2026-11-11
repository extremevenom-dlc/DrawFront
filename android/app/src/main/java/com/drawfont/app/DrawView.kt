package com.drawfont.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.view.MotionEvent
import android.view.View
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

/**
 * The drawing pad. Works in font units (see Stroke) and converts to pixels for display,
 * so what you draw here is exactly what ends up in the font.
 */
class DrawView(context: Context) : View(context) {
    var strokes: MutableList<Stroke> = mutableListOf()
    var eraser = false
    var penWidth = 50f
    var hint = ""
    var onBeforeEdit: () -> Unit = {}
    var onEdited: () -> Unit = {}

    private var live: Stroke? = null
    private var snapshotTaken = false
    private val density = resources.displayMetrics.density

    private val ink = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF222222.toInt()
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val dot = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFF222222.toInt() }
    private val guidePaint = Paint().apply {
        style = Paint.Style.STROKE
        strokeWidth = 2f
        pathEffect = DashPathEffect(floatArrayOf(14f, 9f), 0f)
    }
    private val labelPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val hintPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFECECEC.toInt()
        textAlign = Paint.Align.CENTER
    }

    private val guides = listOf(
        Triple(800f, "ascender", 0xFFBBBBBB.toInt()),
        Triple(700f, "capital", 0xFF7FB0FF.toInt()),
        Triple(500f, "x-height", 0xFF7FB0FF.toInt()),
        Triple(0f, "baseline", 0xFFFF7A7A.toInt()),
        Triple(-200f, "descender", 0xFFBBBBBB.toInt())
    )

    // font units <-> pixels. The view shows y from 950 (top) down to -250 (bottom).
    private fun scale(): Float = if (height > 0) height / 1200f else 1f
    private fun toPx(x: Float): Float = (x + 50f) * scale()
    private fun toPy(y: Float): Float = (950f - y) * scale()
    private fun toFx(px: Float): Float = px / scale() - 50f
    private fun toFy(py: Float): Float = 950f - py / scale()

    override fun onDraw(canvas: Canvas) {
        canvas.drawColor(Color.WHITE)
        val s = scale()
        labelPaint.textSize = 11f * density
        for (g in guides) {
            val y = toPy(g.first)
            guidePaint.color = g.third
            canvas.drawLine(0f, y, width.toFloat(), y, guidePaint)
            labelPaint.color = g.third
            canvas.drawText(g.second, width - 6f * density - labelPaint.measureText(g.second), y - 4f * density, labelPaint)
        }
        if (hint.isNotEmpty()) {
            hintPaint.textSize = 700f * s * (if (hint.length == 1) 0.7f else 0.25f)
            canvas.drawText(hint, width / 2f, toPy(350f) + hintPaint.textSize * 0.35f, hintPaint)
        }
        for (st in strokes) drawStroke(canvas, st, s)
        live?.let { drawStroke(canvas, it, s) }
    }

    private fun drawStroke(c: Canvas, st: Stroke, s: Float) {
        val w = st.w * s
        if (st.pts.size == 1) {
            c.drawCircle(toPx(st.pts[0][0]), toPy(st.pts[0][1]), w / 2f, dot)
            return
        }
        ink.strokeWidth = w
        val path = Path()
        path.moveTo(toPx(st.pts[0][0]), toPy(st.pts[0][1]))
        for (i in 1 until st.pts.size) path.lineTo(toPx(st.pts[i][0]), toPy(st.pts[i][1]))
        c.drawPath(path, ink)
    }

    override fun onTouchEvent(e: MotionEvent): Boolean {
        parent?.requestDisallowInterceptTouchEvent(true)
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                snapshotTaken = false
                if (eraser) {
                    eraseAt(e.x, e.y)
                } else {
                    live = Stroke(penWidth, mutableListOf(floatArrayOf(toFx(e.x), toFy(e.y))))
                }
            }
            MotionEvent.ACTION_MOVE -> {
                for (i in 0 until e.historySize) move(e.getHistoricalX(i), e.getHistoricalY(i))
                move(e.x, e.y)
            }
            MotionEvent.ACTION_UP -> {
                move(e.x, e.y)
                val st = live
                if (st != null) {
                    onBeforeEdit()
                    strokes.add(st)
                    live = null
                    onEdited()
                }
            }
            MotionEvent.ACTION_CANCEL -> live = null
        }
        invalidate()
        return true
    }

    private fun move(x: Float, y: Float) {
        if (eraser) {
            eraseAt(x, y)
            return
        }
        val st = live ?: return
        val last = st.pts.last()
        val nx = toFx(min(max(x, 0f), width.toFloat()))
        val ny = toFy(min(max(y, 0f), height.toFloat()))
        if (hypot(nx - last[0], ny - last[1]) * scale() < 2f * density) return   // ignore tiny jitter
        st.pts.add(floatArrayOf(nx, ny))
    }

    private fun eraseAt(px: Float, py: Float) {
        val fx = toFx(px)
        val fy = toFy(py)
        val radius = 16f * density / scale()
        val hit = strokes.filter { distToPolyline(fx, fy, it.pts) <= radius + it.w / 2f }
        if (hit.isEmpty()) return
        if (!snapshotTaken) {
            onBeforeEdit()
            snapshotTaken = true
        }
        strokes.removeAll(hit)
        onEdited()
    }

    private fun distToPolyline(px: Float, py: Float, pts: List<FloatArray>): Float {
        if (pts.size == 1) return hypot(px - pts[0][0], py - pts[0][1])
        var best = Float.MAX_VALUE
        for (i in 0 until pts.size - 1) {
            val ax = pts[i][0]
            val ay = pts[i][1]
            val dx = pts[i + 1][0] - ax
            val dy = pts[i + 1][1] - ay
            val len2 = dx * dx + dy * dy
            val t = if (len2 == 0f) 0f else max(0f, min(1f, ((px - ax) * dx + (py - ay) * dy) / len2))
            best = min(best, hypot(px - (ax + t * dx), py - (ay + t * dy)))
        }
        return best
    }
}
