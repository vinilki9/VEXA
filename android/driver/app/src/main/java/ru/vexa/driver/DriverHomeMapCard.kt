package ru.vexa.driver

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject

@Composable
internal fun DriverHomeMapCard(
    cityName: String,
    followGps: Boolean,
    activeOrder: JSONObject?
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("VEXA MAP", style = MaterialTheme.typography.titleMedium)
            Text("Ваше местоположение · $cityName",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall)
            DriverMap(
                autoCenter = followGps,
                modifier = Modifier.fillMaxWidth().height(320.dp),
                activeOrder = activeOrder
            )
        }
    }
}
