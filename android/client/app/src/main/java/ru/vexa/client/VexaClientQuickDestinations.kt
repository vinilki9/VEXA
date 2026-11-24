package ru.vexa.client

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/** Familiar one-tap Home/Work shortcuts, backed only by locations chosen from search. */
@Composable
internal fun VexaClientQuickDestinations(
    home: AddressResult?,
    work: AddressResult?,
    hasSelectedDestination: Boolean,
    canEditRoute: Boolean,
    onUse: (AddressResult) -> Unit,
    onSave: (String) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { home?.let(onUse) }, enabled = canEditRoute && home != null) {
                Text("⌂ Дом")
            }
            OutlinedButton(onClick = { work?.let(onUse) }, enabled = canEditRoute && work != null) {
                Text("▣ Работа")
            }
        }
        if (hasSelectedDestination && canEditRoute) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = { onSave(VexaSavedPlaces.HOME) }) {
                    Text("Сохранить как дом")
                }
                TextButton(onClick = { onSave(VexaSavedPlaces.WORK) }) {
                    Text("Как работу")
                }
            }
        } else if (home == null && work == null) {
            Text("Выберите адрес назначения, чтобы сохранить Дом или Работу")
        }
    }
}
