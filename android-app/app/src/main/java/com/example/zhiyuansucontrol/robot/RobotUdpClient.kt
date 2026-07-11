package com.example.zhiyuansucontrol.robot

import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

private const val ROBOT_HOST = "192.168.4.1"
private const val ROBOT_PORT = 9999
private const val ROBOT_PASSWORD = "88888888"

enum class Motion {
    FORWARD,
    BACKWARD,
    LEFT,
    RIGHT,
    TURN_LEFT,
    TURN_RIGHT,
}

enum class RobotAction(val id: Int, val label: String) {
    BASIC_ATTACK(4, "普攻"),
}

data class DriveCommand(
    val angle: Int = 0,
    val speed: Int = 0,
    val turn: Int = 0,
)

/** Sends the documented robot packets directly over the MYAP Wi-Fi network. */
class RobotUdpClient(
    private val robotHost: String = ROBOT_HOST,
    private val password: String = ROBOT_PASSWORD,
) {
    private val commandMutex = Mutex()
    private var lastOutboundPacketAtMillis = 0L
    private var socket: DatagramSocket? = null

    suspend fun nudge(motion: Motion, requestedSpeed: Int, durationMillis: Int = 300) {
        commandMutex.withLock {
            sendMotionLocked(motion, requestedSpeed)

            // Use the same movement packet already verified by the Python controller, then stop it.
            delay((durationMillis.coerceIn(100, 600) + 80).toLong())
            sendStopLocked()
        }
    }

    /** Starts one stream of movement packets. Call [continueMotion] while the control is held. */
    suspend fun startMotion(motion: Motion, requestedSpeed: Int) {
        commandMutex.withLock {
            sendMotionLocked(motion, requestedSpeed)
        }
    }

    /** Sends the next movement packet without waiting for a robot response. */
    suspend fun continueMotion(motion: Motion, requestedSpeed: Int) {
        commandMutex.withLock {
            sendMotionLocked(motion, requestedSpeed)
        }
    }

    suspend fun startDrive(command: DriveCommand) {
        commandMutex.withLock {
            sendDriveLocked(command)
        }
    }

    suspend fun continueDrive(command: DriveCommand) {
        commandMutex.withLock {
            sendDriveLocked(command)
        }
    }

    suspend fun stop() {
        commandMutex.withLock {
            authorizeIfNeeded()
            sendStopLocked()
        }
    }

    suspend fun runAction(actionId: Int) {
        commandMutex.withLock {
            authorizeIfNeeded()
            sendAndCollect(shortPacket(0x07, 0x55, byteArrayOf(actionId.coerceIn(0, 8).toByte())), 0)
        }
    }

    private fun authorizeIfNeeded() {
        // Any valid data packet keeps the robot authorization alive for five seconds.
        // During a held direction button, movement packets arrive every 80 ms.
        if (System.currentTimeMillis() - lastOutboundPacketAtMillis < 4_000) {
            return
        }

        val replies = sendAndCollect(
            shortPacket(0x0A, 0x71, password.toByteArray(Charsets.US_ASCII)),
            250,
        )
        if (replies.any(::isAuthorizationSuccess)) {
            return
        }
        error("未收到机器人的授权成功回包。请确认手机已连接 MYAP 热点。")
    }

    private fun sendAndCollect(packet: ByteArray, waitMillis: Int): List<ByteArray> {
        val robotAddress = InetAddress.getByName(robotHost)
        val replies = mutableListOf<ByteArray>()
        val udpSocket = getSocket()
        udpSocket.send(DatagramPacket(packet, packet.size, robotAddress, ROBOT_PORT))
        lastOutboundPacketAtMillis = System.currentTimeMillis()

        val deadline = System.currentTimeMillis() + waitMillis
        while (System.currentTimeMillis() < deadline) {
            val remaining = (deadline - System.currentTimeMillis()).coerceAtLeast(1).toInt()
            udpSocket.soTimeout = minOf(100, remaining)
            val buffer = ByteArray(2048)
            val response = DatagramPacket(buffer, buffer.size)
            try {
                udpSocket.receive(response)
                replies += response.data.copyOf(response.length)
            } catch (_: SocketTimeoutException) {
                // Keep waiting until the command-specific deadline expires.
            }
        }
        return replies
    }

    private fun getSocket(): DatagramSocket {
        val existing = socket
        if (existing != null && !existing.isClosed) {
            return existing
        }
        return DatagramSocket(null).also { newSocket ->
            newSocket.reuseAddress = true
            newSocket.bind(InetSocketAddress(ROBOT_PORT))
            socket = newSocket
        }
    }

    private fun sendMotionLocked(motion: Motion, requestedSpeed: Int) {
        authorizeIfNeeded()
        val speed = requestedSpeed.coerceIn(5, 25)
        val (angle, linearSpeed, turn) = when (motion) {
            Motion.FORWARD -> Triple(0, speed, 0)
            Motion.BACKWARD -> Triple(180, speed, 0)
            Motion.LEFT -> Triple(90, speed, 0)
            Motion.RIGHT -> Triple(270, speed, 0)
            Motion.TURN_LEFT -> Triple(0, 0, 180)
            Motion.TURN_RIGHT -> Triple(0, 0, -180)
        }
        sendDriveLocked(DriveCommand(angle, linearSpeed, turn))
    }

    private fun sendDriveLocked(command: DriveCommand) {
        authorizeIfNeeded()
        val angle = command.angle.mod(360)
        val speed = command.speed.coerceIn(0, 25)
        val turn = command.turn.coerceIn(-350, 350)
        sendAndCollect(movePacket(angle, speed, turn), 0)
    }

    private fun sendStopLocked() {
        // When the robot is already moving, authorization is still valid. Do not wait here.
        sendAndCollect(movePacket(0, 0, 0), 0)
    }

    private fun isAuthorizationSuccess(raw: ByteArray): Boolean {
        return isValidShortPacket(raw) &&
            raw.size >= 10 &&
            raw[5].unsigned() == 0x0A &&
            raw[6].unsigned() == 0x71 &&
            raw[8].unsigned() == 0x01
    }

    private fun movePacket(angle: Int, speed: Int, turn: Int): ByteArray {
        return shortPacket(0x08, 0x02, int16Le(angle) + int16Le(speed) + int16Le(turn))
    }

    private fun shortPacket(device: Int, command: Int, params: ByteArray): ByteArray {
        val data = byteArrayOf(device.toByte(), command.toByte(), params.size.toByte()) + params
        val body = byteArrayOf(0x00, 0x00, data.size.toByte()) + data
        return byteArrayOf(0xFE.toByte(), 0xEF.toByte()) + body + byteArrayOf(checksum(body))
    }

    private fun isValidShortPacket(raw: ByteArray): Boolean {
        if (raw.size < 7 || raw[0].unsigned() != 0xFE || raw[1].unsigned() != 0xEF) {
            return false
        }
        val dataLength = raw[4].unsigned()
        val dataEnd = 5 + dataLength
        if (raw.size < dataEnd + 1) {
            return false
        }
        return checksum(raw.copyOfRange(2, dataEnd)) == raw[dataEnd]
    }

    private fun int16Le(value: Int): ByteArray {
        val safeValue = value.coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
        return byteArrayOf(
            (safeValue and 0xFF).toByte(),
            ((safeValue ushr 8) and 0xFF).toByte(),
        )
    }

    private fun checksum(body: ByteArray): Byte {
        var sum = 0
        body.forEach { sum = (sum + it.unsigned()) and 0xFF }
        return (sum.inv() and 0xFF).toByte()
    }
}

private fun Byte.unsigned(): Int = toInt() and 0xFF
