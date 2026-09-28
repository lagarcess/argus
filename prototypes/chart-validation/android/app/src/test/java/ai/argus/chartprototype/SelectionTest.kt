package ai.argus.chartprototype
import org.junit.Assert.*
import org.junit.Test
import java.time.LocalDate
import java.util.Locale

class SelectionTest {
    private val first = LocalDate.of(2026, 1, 2)
    @Test fun datesUseElapsedDaysNotRowIndexAndTiesChooseEarlier() {
        val points = listOf(0L, 2L, 10L).map { Sample(first.plusDays(it), 10.0, null, null) }
        assertEquals(1, nearest(points, .5f))
        assertEquals(0, nearest(points.take(2), .5f))
        assertEquals(0, nearest(points, -1f))
        assertEquals(2, nearest(points, 2f))
        assertNull(nearest(emptyList(), .5f))
        assertEquals(0, nearest(points.take(1), 1f))
    }
    @Test fun nullTerminatesEachSeriesIndependently() {
        val rows = listOf(Sample(first, -10.0, null, null), Sample(first.plusDays(1), null, 2.0, null), Sample(first.plusDays(2), 20.0, 3.0, 10.0))
        assertEquals(listOf(1,1,2), segments(rows).map { it.points.size })
        assertEquals("USD -10.00", amount(rows.first().actual, "USD", Locale.US))
        assertEquals("Sin datos", amount(null, "DOP", Locale.forLanguageTag("es-419")))
    }
}
