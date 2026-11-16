
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
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
    val backgroundColor = Color(0xFFF5F7FA)
    val foregroundColor = Color(0xFF111827)
    val secondaryText = Color(0xFF64748B)

    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Color(0xFF20C6B7),
            background = backgroundColor,
            surface = Color.White,
            onBackground = foregroundColor,
            onSurface = foregroundColor
        )
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
                    text = "Финансы",
                    color = foregroundColor,
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Bold
                )

                Spacer(modifier = Modifier.height(16.dp))

                DriverFinancePanel(
                    dark = false,
                    foregroundColor = foregroundColor,
                    secondaryText = secondaryText
                )
            }
        }
    }
}
