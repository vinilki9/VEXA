
package ru.vexa.driver

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

class DriverFinanceActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            VexaFinanceScreen()
        }
    }
}

@Composable
private fun VexaFinanceScreen() {
    val context = LocalContext.current
    val selectedTheme = remember(context) { DriverPreferences.load(context).theme }
    val dark = selectedTheme == "dark" || (selectedTheme == "system" && isSystemInDarkTheme())
    val backgroundColor = if (dark) VexaDesign.graphite else VexaDesign.lightCanvas
    val foregroundColor = if (dark) VexaDesign.textDark else VexaDesign.textLight
    val secondaryText = if (dark) VexaDesign.darkScheme().onSurfaceVariant else VexaDesign.lightScheme().onSurfaceVariant

    MaterialTheme(
        colorScheme = if (dark) VexaDesign.darkScheme() else VexaDesign.lightScheme()
    ) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = backgroundColor
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .background(backgroundColor)
                    .padding(16.dp)
            ) {
                Text(
                    text = "Деньги",
                    color = foregroundColor,
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Bold
                )

                Spacer(modifier = Modifier.height(16.dp))

                DriverFinancePanel(
                    dark = dark,
                    foregroundColor = foregroundColor,
                    secondaryText = secondaryText
                )
            }
        }
    }
}
