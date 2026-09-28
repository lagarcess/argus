package ai.argus.chartprototype

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.*
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import com.patrykandpatrick.vico.compose.cartesian.*
import com.patrykandpatrick.vico.compose.cartesian.layer.*
import com.patrykandpatrick.vico.compose.common.fill
import com.patrykandpatrick.vico.core.cartesian.data.*
import com.patrykandpatrick.vico.core.cartesian.layer.LineCartesianLayer
import com.patrykandpatrick.vico.core.common.component.ShapeComponent
import com.patrykandpatrick.vico.core.common.shape.CorneredShape
import com.patrykandpatrick.vico.core.cartesian.Zoom
import com.patrykandpatrick.vico.compose.cartesian.layer.cartesianLayerPadding
import java.util.Locale

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val cases = assets.open("series.json").bufferedReader().use { parseFixtures(it.readText()) }
        setContent { Prototype(cases) }
    }
}

@Composable
fun Prototype(cases: List<Scenario>) {
    var caseIndex by rememberSaveable { mutableIntStateOf(0) }
    var selected by rememberSaveable { mutableStateOf<Int?>(null) }
    var language by rememberSaveable { mutableStateOf("en") }
    var theme by rememberSaveable { mutableStateOf("System") }
    val es = language == "es-419"
    val locale = Locale.forLanguageTag(if (es) "es-419" else "en-US")
    val scenario = cases[caseIndex]
    fun t(en: String, spanish: String) = if (es) spanish else en
    val dark = theme == "Dark" || (theme == "System" && isSystemInDarkTheme())
    val view = LocalView.current
    SideEffect {
        val window = (view.context as ComponentActivity).window
        WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !dark
    }
    val colors = if (dark) darkColorScheme(primary = Color(0xFF5BA897), onPrimary = Color.Black, background = Color(0xFF0B0B0B), surface = Color(0xFF0B0B0B), surfaceContainer = Color(0xFF202020), onSurface = Color(0xFFF1F1F1)) else lightColorScheme(primary = Color(0xFF287B69), onPrimary = Color.White, background = Color(0xFFFAFAFA), surface = Color(0xFFFAFAFA), surfaceContainer = Color(0xFFF0F0F0), onSurface = Color(0xFF202020))
    MaterialTheme(colorScheme = colors) {
        Surface(Modifier.fillMaxSize().testTag("appearance").semantics { stateDescription = if(dark) "dark" else "light" }) {
            Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).testTag("page").padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Argus", style = MaterialTheme.typography.headlineSmall)
                Text(t("Chart validation · synthetic data", "Validación de gráficos · datos sintéticos"))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { language = if (es) "en" else "es-419" }, modifier = Modifier.testTag("locale")) { Text(if (es) "English" else "Español") }
                    var expanded by remember { mutableStateOf(false) }
                    Box {
                        OutlinedButton(onClick = { expanded = true }, modifier = Modifier.testTag("theme")) { Text(when(theme) { "Dark" -> t("Dark", "Oscuro"); "Light" -> t("Light", "Claro"); else -> t("System", "Sistema") }) }
                        DropdownMenu(expanded, { expanded = false }) { listOf("System", "Light", "Dark").forEach { mode -> DropdownMenuItem(text = { Text(when(mode) { "Dark" -> t("Dark", "Oscuro"); "Light" -> t("Light", "Claro"); else -> t("System", "Sistema") }) }, onClick = { theme = mode; expanded = false }, modifier = Modifier.testTag("theme-$mode")) } }
                    }
                }
                var expanded by remember { mutableStateOf(false) }
                Box {
                    OutlinedButton(onClick = { expanded = true }, modifier = Modifier.testTag("scenario")) { Text(scenario.titles.getValue(language)) }
                    DropdownMenu(expanded, { expanded = false }) { cases.forEachIndexed { index, case -> DropdownMenuItem(text = { Text(case.titles.getValue(language)) }, onClick = { caseIndex = index; selected = null; expanded = false }, modifier = Modifier.testTag("case-${case.id}")) } }
                }
                Text(t("Actual ━   Projected ┄", "Real ━   Proyectado ┄"))
                Text("${scenario.currency} · ${t("major currency units · UTC civil dates", "unidades monetarias · fechas civiles UTC")}", style = MaterialTheme.typography.bodySmall)
                key(scenario.id) { FinancialChart(scenario, selected, { selected = it }, t("No data", "Sin datos")) }
                if (scenario.points.isNotEmpty()) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(date(scenario.points.first().time, locale), style = MaterialTheme.typography.labelSmall)
                    Text(date(scenario.points.last().time, locale), style = MaterialTheme.typography.labelSmall)
                }
                val sample = selected?.let(scenario.points::get)
                val readout = if (sample == null) t("Select a date with the chart or Previous/Next.", "Selecciona una fecha en el gráfico o con Anterior/Siguiente.") else listOf(
                    date(sample.time, locale),
                    t("Actual", "Real") + ": " + amount(sample.actual, scenario.currency, locale),
                    t("Projected", "Proyectado") + ": " + amount(sample.projected, scenario.currency, locale),
                    t("Contribution", "Aporte") + ": " + amount(sample.contribution, scenario.currency, locale)
                ).joinToString("\n")
                Text(readout, Modifier.fillMaxWidth().heightIn(min = 112.dp).testTag("readout").semantics { liveRegion = LiveRegionMode.Polite }, style = MaterialTheme.typography.bodyLarge)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    OutlinedButton(onClick = { selected = selected?.minus(1)?.coerceAtLeast(0) ?: scenario.points.lastIndex }, enabled = scenario.points.isNotEmpty(), modifier = Modifier.testTag("previous")) { Text(t("Previous", "Anterior")) }
                    OutlinedButton(onClick = { selected = selected?.plus(1)?.coerceAtMost(scenario.points.lastIndex) ?: 0 }, enabled = scenario.points.isNotEmpty(), modifier = Modifier.testTag("next")) { Text(t("Next", "Siguiente")) }
                    TextButton(onClick = { selected = null }, modifier = Modifier.testTag("reset")) { Text(t("Reset", "Borrar")) }
                }
                Text(t("Horizontal drag selects. Vertical drag scrolls. Release keeps the date; cancellation restores the prior selection. Missing dates remain selectable.", "Arrastra horizontalmente para seleccionar y verticalmente para desplazar. Al soltar se conserva la fecha; al cancelar se restaura la selección anterior. Las fechas sin datos siguen disponibles."))
                Text(t("Synthetic fixture only. No forecasts, returns, balances, provider calls or account data are calculated here.", "Solo datos sintéticos. Aquí no se calculan pronósticos, rendimientos ni saldos, ni se consultan proveedores o cuentas."))
                Spacer(Modifier.height(280.dp))
                Text(t("End of scroll proof", "Fin de prueba de desplazamiento"), Modifier.testTag("footer"))
            }
        }
    }
}

@Composable
fun FinancialChart(scenario: Scenario, selection: Int?, onSelect: (Int?) -> Unit, empty: String) {
    val pieces = remember(scenario) { segments(scenario.points) }
    val currentSelection by rememberUpdatedState(selection)
    val currentSelect by rememberUpdatedState(onSelect)
    val foreground = MaterialTheme.colorScheme.onSurface
    Box(Modifier.fillMaxWidth().height(220.dp).testTag("chart")) {
        if (pieces.isEmpty()) Text(empty, Modifier.align(Alignment.Center)) else {
            val lines = pieces.map { piece ->
                val color = if (piece.projected) Color(0xFFC88732) else Color(0xFF3D9986)
                val lineFill = LineCartesianLayer.LineFill.single(fill(color))
                LineCartesianLayer.rememberLine(
                    fill = lineFill,
                    stroke = if (piece.projected) LineCartesianLayer.LineStroke.dashed() else LineCartesianLayer.LineStroke.continuous(),
                    pointConnector = LineCartesianLayer.PointConnector.Sharp,
                    pointProvider = if (piece.points.size == 1) LineCartesianLayer.PointProvider.single(LineCartesianLayer.Point(ShapeComponent(fill(color), CorneredShape.Pill), 7f)) else null
                )
            }
            val model = remember(scenario) { CartesianChartModel(LineCartesianLayerModel.build {
                pieces.forEach { piece -> series(piece.points.map { it.time.toEpochDay() }, piece.points.map { (if (piece.projected) it.projected else it.actual)!! }) }
            }) }
            val first = scenario.points.first().time.toEpochDay().toDouble()
            val last = scenario.points.last().time.toEpochDay().toDouble()
            val range = remember(scenario) { CartesianLayerRangeProvider.fixed(minX = if(first == last) first - .5 else first, maxX = if(first == last) last + .5 else last) }
            CartesianChartHost(
                chart = rememberCartesianChart(rememberLineCartesianLayer(lineProvider = LineCartesianLayer.LineProvider.series(lines), rangeProvider = range), layerPadding = { cartesianLayerPadding() }),
                model = model,
                modifier = Modifier.fillMaxSize(),
                scrollState = rememberVicoScrollState(scrollEnabled = false),
                zoomState = rememberVicoZoomState(zoomEnabled = false, initialZoom = Zoom.Content)
            )
        }
        Canvas(Modifier.fillMaxSize().testTag("scrub").pointerInput(scenario.id) {
            var before: Int? = null
            detectHorizontalDragGestures(
                onDragStart = { offset -> before = currentSelection; currentSelect(nearest(scenario.points, offset.x / size.width)) },
                onHorizontalDrag = { change, _ -> currentSelect(nearest(scenario.points, change.position.x / size.width)); change.consume() },
                onDragEnd = {},
                onDragCancel = { currentSelect(before) }
            )
        }.semantics { contentDescription = if(empty == "Sin datos") "Gráfico. Usa Anterior y Siguiente para leer todas las fechas." else "Chart. Use Previous and Next to read every date." }) {
            selection?.let { val x = position(scenario.points, it) * size.width; drawLine(foreground, Offset(x, 0f), Offset(x, size.height), 2f) }
        }
    }
}
