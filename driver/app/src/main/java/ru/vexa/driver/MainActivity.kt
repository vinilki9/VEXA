package ru.vexa.driver

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val Teal = Color(0xFF20C6B7)
private val Ink = Color(0xFF111827)
private val Navy = Color(0xFF1E293B)
class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); setContent { DriverScreen() } }
}
@Composable fun DriverScreen() {
 var online by remember { mutableStateOf(false) }
 var theme by remember { mutableStateOf("Системная") }
 var sound by remember { mutableStateOf("classic") }
 val dark = theme=="Ночная" || (theme=="Системная" && isSystemInDarkTheme())
 val bg=if(dark) Ink else Color(0xFFF5F7FA)
 val fg=if(dark) Color.White else Ink
 Surface(color=bg, modifier=Modifier.fillMaxSize()) {
  Column(Modifier.fillMaxSize().padding(20.dp),verticalArrangement=Arrangement.spacedBy(14.dp)) {
   Row { Text("VEXA",color=Teal,fontSize=25.sp); Spacer(Modifier.width(10.dp)); Text("ВОДИТЕЛЬ",color=fg) }
   Row(verticalAlignment=androidx.compose.ui.Alignment.CenterVertically) { Text(if(online) "На линии" else "Не на линии",color=fg); Spacer(Modifier.weight(1f)); Switch(online,{online=it},colors=SwitchDefaults.colors(checkedThumbColor=Teal,checkedTrackColor=Teal.copy(alpha=.4f))) }
   Box(Modifier.fillMaxWidth().height(210.dp).background(if(dark) Navy else Color(0xFFDDEBE8),RoundedCornerShape(18.dp)).padding(16.dp)) {
    Text("КАРТА · ЗОНЫ СПРОСА · GPS ДЕМО",color=if(dark) Teal else Color(0xFF46716D),fontSize=12.sp)
   }
   Card(colors=CardDefaults.cardColors(containerColor=if(dark) Navy else Color.White)) {
    Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
     Text("Новый заказ · демонстрация",color=fg,style=MaterialTheme.typography.titleMedium)
     Text("Подача: Центральный район",color=fg)
     Text("До пассажира: 4 мин · 1,2 км",color=fg)
     Button(onClick={},colors=ButtonDefaults.buttonColors(containerColor=Teal)) { Text("Принять · демо",color=Ink) }
    }
   }
   Text("Тема приложения",color=fg)
   Row(horizontalArrangement=Arrangement.spacedBy(6.dp)) { listOf("Дневная","Ночная","Системная").forEach { FilterChip(selected=theme==it,onClick={theme=it},label={Text(it)},colors=FilterChipDefaults.filterChipColors(selectedContainerColor=Teal.copy(alpha=.2f))) } }
   Text("Звуковой профиль",color=fg)
   Row(horizontalArrangement=Arrangement.spacedBy(6.dp)) { listOf("classic","modern","soft","dynamic","calm","premium").forEach { FilterChip(selected=sound==it,onClick={sound=it},label={Text(it,fontSize=9.sp)}) } }
   Text("Голосовые команды: «Принять», «Маршрут», «Диспетчер»",color=fg,fontSize=11.sp)
   Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) { listOf("Маршрут","Диспетчер","SOS").forEach { OutlinedButton(onClick={}) { Text(it,color=fg) } } }
   Text("Демо-макет: GPS, заказы и кнопки не подключены к Backend.",color=Color.Gray,fontSize=10.sp)
  }
 }
}
