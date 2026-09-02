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
import android.provider.DocumentsContract
import android.provider.Settings
import android.view.ViewGroup
import android.webkit.WebSettings
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
 * LanShare Android：
 * - WebView 加载“固化”的本地管理面板（assets/admin.html），管理服务未启动也能看界面
 * - 系统文件选择器（SAF）选取要共享的目录/文件，无需手工输入路径
 * - Chaquopy 在主线程初始化后自动运行内嵌 Python 服务
 */
class MainActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var status: TextView
    private val adminUrl = "http://127.0.0.1:8765/"
    private val assetPage = "file:///android_asset/admin.html"
    private val REQ_DIR = 1001
    private val REQ_FILE = 1002

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        status = TextView(this).apply {
            text = "正在启动服务…"
            textSize = 14f
            setPadding(16, 12, 16, 0)
        }
        root.addView(status)

        fun mkBtn(label: String, act: () -> Unit) = Button(this).apply {
            text = label
            textSize = 12f
            isAllCaps = false
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            setOnClickListener { act() }
        }
        val rowA = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(16, 6, 16, 2)
        }
        rowA.addView(mkBtn("刷新面板") { loadPanel() })
        rowA.addView(mkBtn("浏览器打开") { openBrowser() })
        root.addView(rowA)

        val rowB = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(16, 2, 16, 6)
        }
        rowB.addView(mkBtn("共享目录") { pickDir() })
        rowB.addView(mkBtn("共享文件") { pickFile() })
        rowB.addView(mkBtn("文件权限") { openAllFiles() })
        root.addView(rowB)

        web = WebView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
            )
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            // 允许 file:// 页面访问 http://127.0.0.1（本机管理服务）
            settings.setAllowUniversalAccessFromFileURLs(true)
            settings.setAllowFileAccessFromFileURLs(true)
            settings.mediaPlaybackRequiresUserGesture = false
            webViewClient = WebViewClient()
        }
        root.addView(web)
        setContentView(root)

        // 先加载固化面板（不依赖服务）
        loadPanel()

        requestLegacyRead()
        // Chaquopy 官方要求：主线程初始化 Python
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

    // ========== 系统文件选择器（需求2：手动选取共享对象，不手工输路径） ==========
    private fun pickDir() {
        try {
            startActivityForResult(
                Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
                    .putExtra("android.content.extra.SHOW_ADVANCED", true),
                REQ_DIR
            )
        } catch (e: Exception) {
            toast("无法打开目录选择器：${e.message}")
        }
    }

    private fun pickFile() {
        try {
            startActivityForResult(
                Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                },
                REQ_FILE
            )
        } catch (e: Exception) {
            toast("无法打开文件选择器：${e.message}")
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK || data?.data == null) return
        val uri = data.data!!
        val path: String? = when (requestCode) {
            REQ_DIR -> treeUriToFsPath(uri)
            REQ_FILE -> docUriToFsPath(uri)
            else -> null
        }
        if (path == null) {
            toast("无法把所选内容映射为可共享路径（请授予“所有文件访问”后重试）")
            return
        }
        // 调 Python 设置共享
        thread(name = "set-share") {
            try {
                val py = Python.getInstance().getModule("main")
                val res = py.callAttr("set_share", path).toString()
                runOnUiThread {
                    status.text = "已共享：$path"
                    loadPanel()
                    toast("共享已设置：$res")
                }
            } catch (e: Exception) {
                runOnUiThread { toast("设置共享失败：${e.message}") }
            }
        }
    }

    /** ACTION_OPEN_DOCUMENT_TREE 返回的 tree Uri -> /storage/emulated/0/... */
    private fun treeUriToFsPath(uri: Uri): String? {
        return try {
            val id = DocumentsContract.getTreeDocumentId(uri)   // primary:Download
            docIdToPath(id)
        } catch (e: Exception) {
            null
        }
    }

    /** ACTION_OPEN_DOCUMENT 返回的 document Uri -> /storage/emulated/0/... */
    private fun docUriToFsPath(uri: Uri): String? {
        return try {
            val id = DocumentsContract.getDocumentId(uri)       // primary:Download/xx.apk
            docIdToPath(id)
        } catch (e: Exception) {
            null
        }
    }

    private fun docIdToPath(id: String): String? {
        val idx = id.indexOf(':')
        if (idx <= 0) return null
        val type = id.substring(0, idx)
        val rel = id.substring(idx + 1)
        return when (type) {
            "primary" -> "${Environment.getExternalStorageDirectory().path}/$rel"
            "home" -> "${Environment.getExternalStorageDirectory().path}/$rel"
            else -> null  // 外置 SD 卡等无法映射，暂不支持
        }
    }

    // ========== 权限（Android 13+ 需要“所有文件访问”） ==========
    private fun requestLegacyRead() {
        if (Build.VERSION.SDK_INT <= 32 &&
            checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE), 1)
        }
    }

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
                toast("已具备文件访问权限")
            }
        } catch (e: Exception) {
            try {
                startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
            } catch (e2: Exception) {
                toast("无法打开设置：${e2.message}")
            }
        }
    }

    private fun openBrowser() {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(adminUrl)))
        } catch (e: Exception) {
            toast("无可用浏览器")
        }
    }

    // ========== 服务就绪 ==========
    private fun startPythonAndWait() {
        var ready = false
        for (i in 0..60) {
            if (portOpen("127.0.0.1", 8765)) { ready = true; break }
            Thread.sleep(500)
        }
        val ip = wifiIp()
        val pyErr = pythonError()
        val msg = when {
            ready -> "管理面板已就绪 · 共享地址 http://$ip:8766"
            pyErr != null -> "服务启动失败：$pyErr\n请把以上文字反馈给开发者"
            else -> "服务启动超时，管理面板仍可使用；请稍后点「刷新面板」"
        }
        runOnUiThread {
            status.text = msg
            if (ready) loadPanel()
        }
    }

    private fun pythonError(): String? = try {
        val mod = Python.getInstance().getModule("main")
        val s = mod.callAttr("get_status").toString().trim()
        if (s.isEmpty() || s == "running") null else s
    } catch (e: Exception) {
        "无法读取 Python 状态：${e.message}"
    }

    // ========== 页面加载 ==========
    private fun loadPanel() {
        try {
            web.loadUrl(assetPage)   // 固化管理面板（本地 assets）
        } catch (e: Exception) {
            toast("加载面板失败：${e.message}")
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

    private fun toast(msg: String) {
        runOnUiThread {
            Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
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
