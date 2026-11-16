package expo.modules.adbinstaller

import android.util.Log
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Executors
import java.util.concurrent.Future

class AdbInstallerModule : Module() {
    companion object {
        private const val TAG = "AdbInstaller"
        private const val ADB_PORT = 5555
        private const val CONNECT_TIMEOUT = 400
        private const val ADB_TIMEOUT = 10000

        private const val A_CNXN = 0x4e584e43.toInt()
        private const val A_AUTH = 0x48545541.toInt()
        private const val A_OPEN = 0x4e45504f.toInt()
        private const val A_OKAY = 0x59414b4f.toInt()
        private const val A_WRTE = 0x45545257.toInt()
        private const val A_CLSE = 0x45534c43.toInt()

        private const val ADB_VERSION = 0x01000000
        private const val MAX_PAYLOAD = 256 * 1024
    }

    override fun definition() = ModuleDefinition {
        Name("AdbInstaller")

        AsyncFunction("scan") { subnetPrefix: String ->
            scanNetwork(subnetPrefix)
        }

        AsyncFunction("install") { ip: String, apkPath: String ->
            installApk(ip, apkPath)
        }

        AsyncFunction("getLocalSubnet") {
            getSubnet()
        }
    }

    private fun getSubnet(): String? {
        try {
            val interfaces = java.net.NetworkInterface.getNetworkInterfaces() ?: return null
            for (ni in interfaces) {
                if (ni.isLoopback || !ni.isUp) continue
                for (addr in ni.inetAddresses) {
                    if (addr is java.net.Inet4Address && !addr.isLoopbackAddress) {
                        val ip = addr.hostAddress ?: continue
                        val parts = ip.split(".")
                        if (parts.size == 4) return "${parts[0]}.${parts[1]}.${parts[2]}."
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "getSubnet error", e)
        }
        return null
    }

    private fun scanNetwork(subnetPrefix: String): List<Map<String, String>> {
        val found = mutableListOf<Map<String, String>>()
        val threads = mutableListOf<Thread>()

        for (i in 1..254) {
            val ip = "$subnetPrefix$i"
            val t = Thread {
                try {
                    val sock = Socket()
                    sock.connect(InetSocketAddress(ip, ADB_PORT), CONNECT_TIMEOUT)
                    sock.close()
                    synchronized(found) {
                        found.add(mapOf("ip" to ip))
                    }
                } catch (_: Exception) {}
            }
            t.start()
            threads.add(t)
        }
        threads.forEach { it.join(2000) }

        // get model for each found device
        return found.map { entry ->
            val ip = entry["ip"]!!
            val modelo = try { getDeviceModel(ip) } catch (_: Exception) { "Android" }
            mapOf("ip" to ip, "modelo" to modelo)
        }.sortedBy { it["ip"] }
    }

    private fun getDeviceModel(ip: String): String {
        val sock = Socket()
        try {
            sock.connect(InetSocketAddress(ip, ADB_PORT), ADB_TIMEOUT)
            sock.soTimeout = ADB_TIMEOUT
            val inp = sock.getInputStream()
            val out = sock.getOutputStream()

            sendCnxn(out)
            val resp = readMessage(inp)
            if (resp.command != A_CNXN && resp.command != A_AUTH) return "Android"
            if (resp.command == A_AUTH) return "Android"

            val shell = "shell:getprop ro.product.model\u0000"
            val localId = 1
            sendOpen(out, localId, shell)

            var modelo = "Android"
            val deadline = System.currentTimeMillis() + 5000
            while (System.currentTimeMillis() < deadline) {
                val msg = readMessage(inp)
                when (msg.command) {
                    A_OKAY -> {}
                    A_WRTE -> {
                        sendOkay(out, localId, msg.arg0)
                        val text = String(msg.data).trim()
                        if (text.isNotEmpty()) modelo = text
                    }
                    A_CLSE -> break
                    else -> break
                }
            }
            return modelo
        } finally {
            try { sock.close() } catch (_: Exception) {}
        }
    }

    private fun installApk(ip: String, apkPath: String): Map<String, Any> {
        val path = if (apkPath.startsWith("file://")) android.net.Uri.parse(apkPath).path ?: apkPath else apkPath
        val file = File(path)
        if (!file.exists()) return mapOf("ok" to false, "erro" to "APK não encontrado: $path")

        val sock = Socket()
        try {
            sock.connect(InetSocketAddress(ip, ADB_PORT), ADB_TIMEOUT)
            sock.soTimeout = 30000
            val inp = sock.getInputStream()
            val out = sock.getOutputStream()

            // CNXN handshake
            sendCnxn(out)
            val cnxnResp = readMessage(inp)
            if (cnxnResp.command == A_AUTH) {
                return mapOf("ok" to false, "erro" to "A TV pediu autorização ADB. Aceite na tela da TV e tente de novo.")
            }
            if (cnxnResp.command != A_CNXN) {
                return mapOf("ok" to false, "erro" to "Falha na conexão ADB")
            }

            val remoteMaxPayload = cnxnResp.arg1.coerceAtMost(MAX_PAYLOAD)

            // Push APK to /data/local/tmp/rodrigoflix.apk via sync
            val remotePath = "/data/local/tmp/rodrigoflix.apk"
            val localId = 1

            // Open sync: stream
            sendOpen(out, localId, "sync:\u0000")
            var remoteId = 0
            val deadline1 = System.currentTimeMillis() + 10000
            while (System.currentTimeMillis() < deadline1) {
                val msg = readMessage(inp)
                if (msg.command == A_OKAY) { remoteId = msg.arg0; break }
                if (msg.command == A_CLSE) return mapOf("ok" to false, "erro" to "TV recusou sync")
            }
            if (remoteId == 0) return mapOf("ok" to false, "erro" to "Timeout ao abrir sync")

            // SEND command
            val sendHeader = "SEND"
            val modeStr = "$remotePath,33188"
            val modeBuf = modeStr.toByteArray()
            val sendBuf = ByteBuffer.allocate(8 + modeBuf.size).order(ByteOrder.LITTLE_ENDIAN)
            sendBuf.put(sendHeader.toByteArray())
            sendBuf.putInt(modeBuf.size)
            sendBuf.put(modeBuf)
            sendWrite(out, localId, remoteId, sendBuf.array())
            readOkayOrFail(inp)

            // Send file data in DATA chunks
            val chunkSize = (remoteMaxPayload - 8).coerceAtMost(64 * 1024)
            val fis = file.inputStream()
            val buf = ByteArray(chunkSize)
            var bytesRead: Int
            while (fis.read(buf).also { bytesRead = it } != -1) {
                val dataBuf = ByteBuffer.allocate(8 + bytesRead).order(ByteOrder.LITTLE_ENDIAN)
                dataBuf.put("DATA".toByteArray())
                dataBuf.putInt(bytesRead)
                dataBuf.put(buf, 0, bytesRead)
                sendWrite(out, localId, remoteId, dataBuf.array())
                readOkayOrFail(inp)
            }
            fis.close()

            // DONE with mtime
            val doneBuf = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN)
            doneBuf.put("DONE".toByteArray())
            doneBuf.putInt((System.currentTimeMillis() / 1000).toInt())
            sendWrite(out, localId, remoteId, doneBuf.array())

            // Read OKAY from sync (the sync response after DONE)
            val deadline2 = System.currentTimeMillis() + 10000
            while (System.currentTimeMillis() < deadline2) {
                val msg = readMessage(inp)
                if (msg.command == A_OKAY) break
                if (msg.command == A_WRTE) {
                    sendOkay(out, localId, remoteId)
                    val text = String(msg.data)
                    if (text.startsWith("FAIL")) {
                        return mapOf("ok" to false, "erro" to "Erro ao enviar: ${text.substring(8)}")
                    }
                    break
                }
                if (msg.command == A_CLSE) break
            }

            // Close sync
            sendClose(out, localId, remoteId)

            // Now install: open shell pm install
            val installId = 2
            sendOpen(out, installId, "shell:pm install -r $remotePath\u0000")
            var installRemoteId = 0
            val deadline3 = System.currentTimeMillis() + 10000
            while (System.currentTimeMillis() < deadline3) {
                val msg = readMessage(inp)
                if (msg.command == A_OKAY) { installRemoteId = msg.arg0; break }
                if (msg.command == A_CLSE) return mapOf("ok" to false, "erro" to "TV recusou instalação")
            }

            // Wait for install result
            val output = StringBuilder()
            sock.soTimeout = 300000 // 5 min for large APK install
            val deadline4 = System.currentTimeMillis() + 300000
            while (System.currentTimeMillis() < deadline4) {
                val msg = readMessage(inp)
                when (msg.command) {
                    A_WRTE -> {
                        sendOkay(out, installId, installRemoteId)
                        output.append(String(msg.data))
                    }
                    A_CLSE -> break
                    A_OKAY -> {}
                    else -> break
                }
            }

            val result = output.toString().trim()
            return if (result.contains("Success", ignoreCase = true)) {
                mapOf("ok" to true, "msg" to "RodrigoFlix instalado com sucesso!")
            } else {
                mapOf("ok" to false, "erro" to "Falha: $result")
            }
        } catch (e: Exception) {
            Log.e(TAG, "installApk error", e)
            return mapOf("ok" to false, "erro" to "Erro: ${e.message}")
        } finally {
            try { sock.close() } catch (_: Exception) {}
        }
    }

    // ADB protocol helpers
    data class AdbMessage(val command: Int, val arg0: Int, val arg1: Int, val data: ByteArray)

    private fun sendMessage(out: OutputStream, command: Int, arg0: Int, arg1: Int, data: ByteArray = ByteArray(0)) {
        val header = ByteBuffer.allocate(24).order(ByteOrder.LITTLE_ENDIAN)
        header.putInt(command)
        header.putInt(arg0)
        header.putInt(arg1)
        header.putInt(data.size)
        var checksum = 0
        for (b in data) checksum += (b.toInt() and 0xFF)
        header.putInt(checksum)
        header.putInt(command xor -1)
        out.write(header.array())
        if (data.isNotEmpty()) out.write(data)
        out.flush()
    }

    private fun readMessage(inp: InputStream): AdbMessage {
        val header = readExact(inp, 24)
        val buf = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN)
        val command = buf.getInt()
        val arg0 = buf.getInt()
        val arg1 = buf.getInt()
        val dataLen = buf.getInt()
        buf.getInt() // checksum
        buf.getInt() // magic
        val data = if (dataLen > 0) readExact(inp, dataLen) else ByteArray(0)
        return AdbMessage(command, arg0, arg1, data)
    }

    private fun readExact(inp: InputStream, len: Int): ByteArray {
        val buf = ByteArray(len)
        var off = 0
        while (off < len) {
            val n = inp.read(buf, off, len - off)
            if (n == -1) throw java.io.IOException("EOF")
            off += n
        }
        return buf
    }

    private fun sendCnxn(out: OutputStream) {
        val banner = "host::features=shell_v2,cmd".toByteArray()
        sendMessage(out, A_CNXN, ADB_VERSION, MAX_PAYLOAD, banner)
    }

    private fun sendOpen(out: OutputStream, localId: Int, destination: String) {
        sendMessage(out, A_OPEN, localId, 0, destination.toByteArray())
    }

    private fun sendOkay(out: OutputStream, localId: Int, remoteId: Int) {
        sendMessage(out, A_OKAY, localId, remoteId)
    }

    private fun sendWrite(out: OutputStream, localId: Int, remoteId: Int, data: ByteArray) {
        sendMessage(out, A_WRTE, localId, remoteId, data)
    }

    private fun sendClose(out: OutputStream, localId: Int, remoteId: Int) {
        sendMessage(out, A_CLSE, localId, remoteId)
    }

    private fun readOkayOrFail(inp: InputStream): AdbMessage {
        val msg = readMessage(inp)
        if (msg.command != A_OKAY && msg.command != A_WRTE) {
            throw java.io.IOException("Expected OKAY, got ${msg.command}")
        }
        return msg
    }
}
