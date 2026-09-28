package ai.argus.foundation.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathBuilder
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.unit.dp

/** Small native vectors keep the foundation independent of a second icon catalog. */
internal object ArgusIcons {
    private fun icon(name: String, block: PathBuilder.() -> Unit) =
        ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f).apply {
            path(
                fill = null, stroke = SolidColor(Color.Black), strokeLineWidth = 1.8f,
                strokeLineCap = StrokeCap.Round, strokeLineJoin = StrokeJoin.Round,
                pathFillType = PathFillType.NonZero, pathBuilder = block,
            )
        }.build()

    val Home = icon("Home") {
        moveTo(3f, 10f); lineTo(12f, 3f); lineTo(21f, 10f); verticalLineTo(21f)
        horizontalLineTo(15f); verticalLineTo(14f); horizontalLineTo(9f)
        verticalLineTo(21f); horizontalLineTo(3f); close()
    }
    val Accounts = icon("Accounts") {
        moveTo(5f, 4f); horizontalLineTo(19f); quadTo(22f, 4f, 22f, 7f)
        verticalLineTo(18f); quadTo(22f, 21f, 19f, 21f); horizontalLineTo(5f)
        quadTo(2f, 21f, 2f, 18f); verticalLineTo(7f); quadTo(2f, 4f, 5f, 4f)
        moveTo(2f, 10f); horizontalLineTo(22f); moveTo(6f, 16f); horizontalLineTo(11f)
    }
    val Plan = icon("Plan") {
        moveTo(12f, 2f); curveTo(25f, 2f, 25f, 22f, 12f, 22f)
        curveTo(-1f, 22f, -1f, 2f, 12f, 2f); close()
        moveTo(12f, 7f); curveTo(19f, 7f, 19f, 17f, 12f, 17f)
        curveTo(5f, 17f, 5f, 7f, 12f, 7f); close()
    }
    val Search = icon("Search") {
        moveTo(10f, 3f); curveTo(20f, 3f, 20f, 17f, 10f, 17f)
        curveTo(0f, 17f, 0f, 3f, 10f, 3f); close()
        moveTo(16f, 16f); lineTo(22f, 22f)
    }
    val Back = icon("Back") { moveTo(15f, 5f); lineTo(8f, 12f); lineTo(15f, 19f) }
    val Next = icon("Next") { moveTo(9f, 5f); lineTo(16f, 12f); lineTo(9f, 19f) }
    val Add = icon("Add") {
        moveTo(12f, 4f); verticalLineTo(20f); moveTo(4f, 12f); horizontalLineTo(20f)
    }
    val Send = icon("Send") {
        moveTo(12f, 20f); verticalLineTo(4f); moveTo(5f, 11f); lineTo(12f, 4f)
        lineTo(19f, 11f)
    }
    val Profile = icon("Profile") {
        moveTo(12f, 3f); curveTo(18f, 3f, 18f, 11f, 12f, 11f)
        curveTo(6f, 11f, 6f, 3f, 12f, 3f); close()
        moveTo(5f, 21f); verticalLineTo(19f); curveTo(5f, 12f, 19f, 12f, 19f, 19f)
        verticalLineTo(21f)
    }
    val Updates = icon("Updates") {
        moveTo(4f, 18f); lineTo(6f, 14f); verticalLineTo(9f)
        curveTo(6f, 1f, 18f, 1f, 18f, 9f); verticalLineTo(14f)
        lineTo(20f, 18f); close(); moveTo(10f, 22f); horizontalLineTo(14f)
    }
    val Recents = icon("Recents") {
        moveTo(3f, 8f); curveTo(8f, -2f, 23f, 2f, 22f, 13f)
        curveTo(21f, 24f, 5f, 24f, 3f, 15f)
        moveTo(3f, 3f); verticalLineTo(8f); horizontalLineTo(8f)
        moveTo(12f, 7f); verticalLineTo(12f); lineTo(16f, 15f)
    }
    val Temporary = icon("Temporary") {
        moveTo(5f, 5f); lineTo(8f, 3f); moveTo(12f, 2f); lineTo(16f, 3f)
        moveTo(20f, 6f); lineTo(22f, 10f); moveTo(22f, 14f); lineTo(20f, 18f)
        moveTo(16f, 21f); lineTo(12f, 22f); moveTo(8f, 21f); lineTo(3f, 22f)
        lineTo(4f, 17f); moveTo(2f, 13f); lineTo(3f, 9f)
    }
    val Microphone = icon("Microphone") {
        moveTo(9f, 5f); curveTo(9f, 1f, 15f, 1f, 15f, 5f); verticalLineTo(12f)
        curveTo(15f, 16f, 9f, 16f, 9f, 12f); close()
        moveTo(5f, 11f); curveTo(5f, 21f, 19f, 21f, 19f, 11f)
        moveTo(12f, 19f); verticalLineTo(23f)
    }
}
