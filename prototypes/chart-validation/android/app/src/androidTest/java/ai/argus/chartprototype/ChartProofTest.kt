package ai.argus.chartprototype

import android.os.SystemClock
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File
import java.util.Locale

class ChartProofTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val cases get() = context.assets.open("series.json").bufferedReader().use { parseFixtures(it.readText()) }
    private fun choose(id: String) {
        compose.onNodeWithTag("scenario").performClick()
        compose.onNodeWithTag("case-$id").performClick()
        compose.waitForIdle()
    }
    private fun readout() = compose.onNodeWithTag("readout").fetchSemanticsNode().config[SemanticsProperties.Text].joinToString { it.text }
    private fun screenshot(name: String) {
        compose.waitForIdle()
        UiDevice.getInstance(InstrumentationRegistry.getInstrumentation()).takeScreenshot(File(context.getExternalFilesDir(null), "$name.png"))
    }
    @Test fun fixturesAndSegmentsPreserveEveryFact() {
        cases.forEach { case ->
            listOf(false, true).forEach { projected ->
                val pieces = segments(case.points).filter { it.projected == projected }
                assertEquals(case.points.filter { (if(projected) it.projected else it.actual) != null }, pieces.flatMap { it.points })
                pieces.forEach { segment ->
                    segment.points.zipWithNext().forEach { (a,b) -> assertEquals(case.points.indexOf(a) + 1, case.points.indexOf(b)) }
                }
            }
            if (case.points.isNotEmpty()) {
                assertEquals(0, nearest(case.points, -1f))
                assertEquals(case.points.lastIndex, nearest(case.points, 2f))
            } else assertNull(nearest(case.points, .5f))
        }
    }
    @Test fun allCasesAccessibleReadoutAndFormatting() {
        for (case in cases) {
            choose(case.id)
            if(case.points.isEmpty()) {
                compose.onNodeWithTag("next").assertIsNotEnabled()
                screenshot("empty")
            } else {
                compose.onNodeWithTag("next").performClick()
                assertTrue(readout().contains(date(case.points.first().time, Locale.US)))
                compose.onNodeWithTag("reset").performClick()
                compose.onNodeWithTag("previous").performClick()
                assertTrue(readout().contains(date(case.points.last().time, Locale.US)))
                screenshot(case.id)
            }
        }
        val stress = cases.first { it.id == "stress" }
        choose(stress.id)
        for (point in stress.points) {
            compose.onNodeWithTag("next").performClick()
            assertTrue(readout().contains(date(point.time, Locale.US)))
            assertTrue(readout().contains("Actual: " + amount(point.actual, stress.currency, Locale.US)))
            assertTrue(readout().contains("Projected: " + amount(point.projected, stress.currency, Locale.US)))
        }
        compose.onNodeWithTag("locale").performClick()
        val spanish = Locale.forLanguageTag("es-419")
        assertTrue(readout().contains(date(stress.points.last().time, spanish)))
        assertTrue(readout().contains("Real: " + amount(stress.points.last().actual, stress.currency, spanish)))
        compose.onNodeWithTag("theme").performClick()
        compose.onNodeWithTag("theme-Dark").performClick()
        screenshot("spanish-dark")
        compose.onNodeWithTag("theme").performClick()
        compose.onNodeWithTag("theme-Light").performClick()
        screenshot("spanish-light")
        compose.onNodeWithTag("theme").performClick()
        compose.onNodeWithTag("theme-System").performClick()
        screenshot("spanish-system")
    }
    @Test fun dragReleaseCancellationResetAndScroll() {
        val stress = cases.first { it.id == "stress" }
        choose(stress.id)
        compose.onNodeWithTag("scrub").performTouchInput { swipe(Offset(1f, centerY), Offset(width.toFloat()-1, centerY), 600) }
        assertTrue(readout().contains(date(stress.points.last().time, Locale.US)))
        screenshot("scrub-endpoint")
        val retained = readout()
        compose.onNodeWithTag("scrub").performTouchInput {
            down(Offset(width.toFloat()-2, centerY))
            moveTo(Offset(width * .4f, centerY), 200)
            cancel()
        }
        assertEquals(retained, readout())
        compose.onNodeWithTag("scrub").performTouchInput { swipe(Offset(width.toFloat()-1, centerY), Offset(1f, centerY), 500) }
        assertTrue(readout().contains(date(stress.points.first().time, Locale.US)))
        compose.onNodeWithTag("reset").performClick()
        assertTrue(readout().startsWith("Select"))
        val before = compose.onNodeWithTag("page").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
        compose.onNodeWithTag("scrub").performTouchInput { swipe(Offset(centerX, height*.9f), Offset(centerX, 1f), 500) }
        val after = compose.onNodeWithTag("page").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
        assertTrue("Vertical chart gesture must scroll page", after > before)
        screenshot("vertical-scroll")
    }
    @Test fun systemAppearanceFollowsDeviceSetting() {
        val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        try {
            device.executeShellCommand("cmd uimode night yes")
            compose.waitUntil(10000) { compose.onNodeWithTag("appearance").fetchSemanticsNode().config[SemanticsProperties.StateDescription] == "dark" }
            screenshot("system-os-dark")
            device.executeShellCommand("cmd uimode night no")
            compose.waitUntil(10000) { compose.onNodeWithTag("appearance").fetchSemanticsNode().config[SemanticsProperties.StateDescription] == "light" }
            screenshot("system-os-light")
        } finally { device.executeShellCommand("cmd uimode night auto") }
    }
    @Test fun longSeriesMeasuredInteraction() {
        val start = SystemClock.elapsedRealtimeNanos()
        choose("long")
        val ready = SystemClock.elapsedRealtimeNanos()
        val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        device.executeShellCommand("dumpsys gfxinfo ai.argus.chartprototype reset")
        val bounds = compose.onNodeWithTag("scrub").fetchSemanticsNode().boundsInWindow
        repeat(12) { n ->
            val a = (if(n % 2 == 0) bounds.left + 1 else bounds.right - 1).toInt()
            val b = (if(n % 2 == 0) bounds.right - 1 else bounds.left + 1).toInt()
            device.swipe(a, bounds.center.y.toInt(), b, bounds.center.y.toInt(), 60)
            compose.waitForIdle()
        }
        val finish = SystemClock.elapsedRealtimeNanos()
        val report = "scenario_switch_to_idle_ms=${(ready-start)/1e6}\n12_uiautomator_60step_swipes_including_test_sync_ms=${(finish-ready)/1e6}\npoints=${cases.first { it.id == "long" }.points.size}\n"
        File(context.getExternalFilesDir(null), "interaction-measurements.txt").writeText(report)
        File(context.getExternalFilesDir(null), "long-series-gfxinfo.txt").writeText(device.executeShellCommand("dumpsys gfxinfo ai.argus.chartprototype framestats"))
        screenshot("long-scrub")
    }
}
