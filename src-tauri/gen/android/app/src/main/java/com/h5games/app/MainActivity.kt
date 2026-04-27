package com.h5games.app

import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.core.view.WindowCompat

class MainActivity : TauriActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    enableEdgeToEdge()
    super.onCreate(savedInstanceState)

    // 系统栏始终可见，内容自动预留系统栏空间
    WindowCompat.setDecorFitsSystemWindows(window, true)
  }
}