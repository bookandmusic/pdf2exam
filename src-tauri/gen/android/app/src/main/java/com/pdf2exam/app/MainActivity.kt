package com.pdf2exam.app

import android.os.Bundle
import android.view.WindowInsets
import android.view.WindowInsetsController
import androidx.activity.enableEdgeToEdge
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsControllerCompat

class MainActivity : TauriActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    enableEdgeToEdge()
    super.onCreate(savedInstanceState)

    // 全屏沉浸式：隐藏状态栏和导航栏，滑动可唤出
    WindowCompat.setDecorFitsSystemWindows(window, false)
    WindowInsetsControllerCompat(window, window.decorView).apply {
      hide(WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars())
      systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
    }
  }

  override fun onResume() {
    super.onResume()
    // 恢复前台时重新隐藏系统栏
    WindowInsetsControllerCompat(window, window.decorView).apply {
      hide(WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars())
      systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
    }
  }
}