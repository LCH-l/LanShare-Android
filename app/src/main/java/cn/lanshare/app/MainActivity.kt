package cn.lanshare.app

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.view.ViewGroup
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.net.InetAddress
import java.net.Socket
import kotlin.concurrent.thread

/**
 * LanShare Android 壳：
 * 启动时在后台线程运行内嵌 Python（LanShare 服务），
 * 界面用 WebView 加载本机 127.0.0.1:8765 管理面板。
 */
class MainActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var status: TextView
    private val adminUrl = "http://127.0.0.1:8765/"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        status = TextView(this).apply {
            text = "正在启动共享服务…"
            textSize = 14f
            setPadding(16, 12, 16, 0)
        }
        root.addView(status)

        fun mkBtn(label: String, act: () -> Unit) = Button(this).apply {
            text = label
            isAllCaps = false
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            setOnClickListener { act() }
        }
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(16, 8, 16, 4)
        }
        bar.addView(mkBtn("刷新面板") { loadPanel() })
        bar.addView(mkBtn("浏览器打开") { openBrowser() })
        if (Build.VERSION.SDK_INT >= 30) {
            bar.addView(mkBtn("文件权限") { openAllFiles() })
        }
        root.addView(bar)

        web = WebView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
            )
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = WebViewClient()
        }
        root.addView(web)
        setContentView(root)

        requestLegacyRead()
        // Chaquopy 要求：Python.start 必须在主线程初始化（官方模式）
        // 初始化耗时约 1-3 秒，期间 UI 保持"正在启动"提示
        try {
            if (!Python.isStarted()) {
                Python.start(AndroidPlatform(this))
            }
        } catch (e: Exception) {
            status.text = "Python 初始化失败：${e.message}\n请把此文字反馈给开发者"
            return
        }
        thread(name = "lanshare-boot") {
            startPythonAndWait()
        }
    }

    /** Android 12 及以下：运行时申请读存储权限 */
    private fun requestLegacyRead() {
        if (Build.VERSION.SDK_INT <= 32 &&
            checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE), 1)
        }
    }

    /** Android 13+：引导授予"所有文件访问" */
    private fun openAllFiles() {
        try {
            if (Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
                startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                        Uri.parse("package:$packageName")
                    )
                )
            } else {
                Toast.makeText(this, "已具备文件访问权限", Toast.LENGTH_SHORT).show()
            }
        } catch (e: Exception) {
            try {
                startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
            } catch (e2: Exception) {
                Toast.makeText(this, "无法打开设置: ${e2.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun openBrowser() {
        runOnUiThread {
            try {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(adminUrl)))
            } catch (e: Exception) {
                Toast.makeText(this, "无可用浏览器", Toast.LENGTH_SHORT).show()
            }
        }
    }

    /** 等待 Chaquopy 执行 main.py 后，管理面板(8765)就绪 */
    private fun startPythonAndWait() {
        var ready = false
        for (i in 0..60) {
            if (portOpen("127.0.0.1", 8765)) { ready = true; break }
            Thread.sleep(500)
        }
        val ip = wifiIp()
        val pyErr = pythonError()
        val msg = when {
            ready -> "管理面板已就绪 · 共享地址 http://$ip:8766\n（如 8766 打不开请点「文件权限」并重启 App）"
            pyErr != null -> "服务启动失败：$pyErr\n请把以上文字反馈给开发者"
            else -> "服务启动超时（30秒），请点「刷新面板」重试"
        }
        runOnUiThread {
            status.text = msg
            if (ready) loadPanel()
        }
    }

    /** 读取 Python 侧记录的启动错误（来自 main.py 的 get_status()） */
    private fun pythonError(): String? = try {
        val mod = Python.getInstance().getModule("main")
        val s = mod.callAttr("get_status").toString().trim()
        if (s.isEmpty() || s == "running") null else s
    } catch (e: Exception) {
        "无法读取 Python 状态：${e.message}"
    }

    private fun loadPanel() {
        try {
            web.loadUrl(adminUrl)
        } catch (e: Exception) {
            Toast.makeText(this, "加载失败: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun portOpen(host: String, port: Int): Boolean = try {
        Socket(host, port).use { true }
    } catch (e: Exception) {
        false
    }

    private fun wifiIp(): String {
        return try {
            val wm = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
            val info = wm.connectionInfo ?: return "本机"
            val i = info.ipAddress
            InetAddress.getByAddress(
                byteArrayOf(
                    (i and 0xff).toByte(),
                    (i shr 8 and 0xff).toByte(),
                    (i shr 16 and 0xff).toByte(),
                    (i shr 24 and 0xff).toByte()
                )
            ).hostAddress ?: "本机"
        } catch (e: Exception) {
            "本机"
        }
    }

    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }
}
