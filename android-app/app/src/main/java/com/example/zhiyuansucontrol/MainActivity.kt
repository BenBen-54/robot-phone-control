package com.example.zhiyuansucontrol

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.example.zhiyuansucontrol.recognition.TaskCardRecognizer
import com.example.zhiyuansucontrol.robot.DriveCommand
import com.example.zhiyuansucontrol.robot.RobotAction
import com.example.zhiyuansucontrol.robot.RobotUdpClient
import com.example.zhiyuansucontrol.ui.theme.ZhiYuanSuDirectControlTheme
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.roundToInt
import kotlin.math.sqrt

private const val CONTROL_INTERVAL_MILLIS = 80L
private const val JOYSTICK_DEAD_ZONE = 0.08f

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ZhiYuanSuDirectControlTheme {
                DirectControlScreen()
            }
        }
    }
}

@Composable
private fun DirectControlScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val robot = remember { RobotUdpClient() }
    val taskRecognizer = remember { TaskCardRecognizer() }
    var speedLimit by rememberSaveable { mutableFloatStateOf(15f) }
    var movementVector by remember { mutableStateOf(Offset.Zero) }
    var turnVector by remember { mutableStateOf(Offset.Zero) }
    var driveCommand by remember { mutableStateOf(DriveCommand()) }
    var controlActive by remember { mutableStateOf(false) }
    var pendingPhotoUri by remember { mutableStateOf<Uri?>(null) }
    var recognitionInProgress by remember { mutableStateOf(false) }
    var status by rememberSaveable { mutableStateOf("请先将手机连接到机器人 MYAP 热点") }

    DisposableEffect(taskRecognizer) {
        onDispose {
            taskRecognizer.close()
        }
    }

    fun updateDriveCommand() {
        val x = movementVector.x
        val y = movementVector.y
        val magnitude = sqrt(x * x + y * y).coerceAtMost(1f)
        val moving = magnitude >= JOYSTICK_DEAD_ZONE
        val angle = if (moving) {
            val degrees = Math.toDegrees(atan2((-x).toDouble(), (-y).toDouble()))
            degrees.roundToInt().mod(360)
        } else {
            0
        }
        val linearSpeed = if (moving) {
            (speedLimit * magnitude).roundToInt().coerceAtLeast(5)
        } else {
            0
        }
        val turn = if (abs(turnVector.x) >= JOYSTICK_DEAD_ZONE) {
            (-turnVector.x * 280).roundToInt().coerceIn(-280, 280)
        } else {
            0
        }
        driveCommand = DriveCommand(angle = angle, speed = linearSpeed, turn = turn)
        controlActive = linearSpeed > 0 || turn != 0
    }

    LaunchedEffect(controlActive) {
        if (!controlActive) {
            return@LaunchedEffect
        }

        var failed = false
        try {
            status = "摇杆控制中..."
            withContext(Dispatchers.IO) {
                robot.startDrive(driveCommand)
            }
            while (isActive && controlActive) {
                delay(CONTROL_INTERVAL_MILLIS)
                val nextCommand = driveCommand
                withContext(Dispatchers.IO) {
                    robot.continueDrive(nextCommand)
                }
            }
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            failed = true
            controlActive = false
            status = "失败：${error.message ?: "无法连接机器人"}"
        } finally {
            if (!controlActive) {
                withContext(NonCancellable + Dispatchers.IO) {
                    robot.stop()
                }
                if (!failed) {
                    status = "机器人已停止"
                }
            }
        }
    }

    fun emergencyStop() {
        movementVector = Offset.Zero
        turnVector = Offset.Zero
        driveCommand = DriveCommand()
        controlActive = false
        status = "停止指令发送中..."
        scope.launch {
            try {
                withContext(Dispatchers.IO) {
                    robot.stop()
                }
                status = "机器人已停止"
            } catch (error: Exception) {
                status = "停止失败：${error.message ?: "无法连接机器人"}"
            }
        }
    }

    fun triggerAction(action: RobotAction) {
        movementVector = Offset.Zero
        turnVector = Offset.Zero
        driveCommand = DriveCommand()
        controlActive = false
        status = "正在发送${action.label}..."
        scope.launch {
            try {
                withContext(Dispatchers.IO) {
                    // Stop first so an action cannot begin while the chassis is still moving.
                    robot.stop()
                    delay(150)
                    robot.runAction(action.id)
                }
                status = "已发送${action.label}"
            } catch (error: Exception) {
                status = "动作失败：${error.message ?: "无法连接机器人"}"
            }
        }
    }

    fun recognizeTaskCard(photoUri: Uri) {
        recognitionInProgress = true
        status = "正在识别任务卡..."
        taskRecognizer.recognize(
            context = context,
            photoUri = photoUri,
            onSuccess = { result ->
                recognitionInProgress = false
                val task = result.task
                if (task == null) {
                    val preview = result.rawText.replace(Regex("\\s+"), " ").take(80)
                    status = if (preview.isBlank()) {
                        "未识别到任务卡文字"
                    } else {
                        "未匹配任务：$preview"
                    }
                } else {
                    movementVector = Offset.Zero
                    turnVector = Offset.Zero
                    driveCommand = DriveCommand()
                    controlActive = false
                    status = "已识别${task.phrase}，正在执行..."
                    scope.launch {
                        try {
                            withContext(Dispatchers.IO) {
                                robot.stop()
                                delay(150)
                            }
                            withContext(Dispatchers.IO) {
                                robot.runAction(task.actionId)
                            }
                            status = "已触发${task.phrase}的机器人动作"
                        } catch (error: Exception) {
                            status = "任务执行失败：${error.message ?: "无法连接机器人"}"
                        }
                    }
                }
            },
            onFailure = { error ->
                recognitionInProgress = false
                status = "识别失败：${error.message ?: "无法读取照片"}"
            },
        )
    }

    fun createPhotoUri(): Uri {
        val directory = File(context.cacheDir, "task_cards")
        directory.mkdirs()
        val photo = File(directory, "task_card_${System.currentTimeMillis()}.jpg")
        return FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            photo,
        )
    }

    val capturePhoto = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture(),
    ) { saved ->
        val photoUri = pendingPhotoUri
        pendingPhotoUri = null
        if (saved && photoUri != null) {
            recognizeTaskCard(photoUri)
        } else {
            status = "已取消拍照"
        }
    }

    fun startCameraCapture() {
        val photoUri = createPhotoUri()
        pendingPhotoUri = photoUri
        capturePhoto.launch(photoUri)
    }

    val requestCameraPermission = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            startCameraCapture()
        } else {
            status = "未获得相机权限，无法识别任务卡"
        }
    }

    fun captureAndRecognize() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startCameraCapture()
        } else {
            requestCameraPermission.launch(Manifest.permission.CAMERA)
        }
    }

    Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 20.dp, vertical = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text("智元素直连控制", style = MaterialTheme.typography.headlineSmall)
            Text("机器人：192.168.4.1:9999", style = MaterialTheme.typography.bodyMedium)

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text("速度上限 ${speedLimit.toInt()}", style = MaterialTheme.typography.titleMedium)
                    Slider(
                        value = speedLimit,
                        onValueChange = {
                            speedLimit = it
                            updateDriveCommand()
                        },
                        valueRange = 5f..25f,
                        steps = 19,
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(18.dp),
            ) {
                VirtualJoystick(
                    label = "移动",
                    modifier = Modifier.weight(1f),
                    onVectorChanged = {
                        movementVector = it
                        updateDriveCommand()
                    },
                )
                VirtualJoystick(
                    label = "转向",
                    modifier = Modifier.weight(1f),
                    onVectorChanged = {
                        turnVector = it
                        updateDriveCommand()
                    },
                )
            }

            Button(
                onClick = ::emergencyStop,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFB3261E)),
            ) {
                Text("停止")
            }

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text("机器人动作", style = MaterialTheme.typography.titleMedium)
                    Button(
                        onClick = { triggerAction(RobotAction.BASIC_ATTACK) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(RobotAction.BASIC_ATTACK.label)
                    }
                }
            }

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text("任务识别", style = MaterialTheme.typography.titleMedium)
                    Button(
                        onClick = ::captureAndRecognize,
                        enabled = !recognitionInProgress,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(if (recognitionInProgress) "识别中" else "拍照识别任务")
                    }
                }
            }

            Card(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = status,
                    modifier = Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun VirtualJoystick(
    label: String,
    modifier: Modifier = Modifier,
    onVectorChanged: (Offset) -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    val latestCallback by rememberUpdatedState(onVectorChanged)
    var layoutSize by remember { mutableStateOf(IntSize.Zero) }
    var thumbOffset by remember { mutableStateOf(Offset.Zero) }

    fun updateThumb(position: Offset?) {
        val minimumSide = minOf(layoutSize.width, layoutSize.height).toFloat()
        val radius = minimumSide * 0.34f
        if (position == null || radius <= 0f) {
            thumbOffset = Offset.Zero
            latestCallback(Offset.Zero)
            return
        }

        val center = Offset(layoutSize.width / 2f, layoutSize.height / 2f)
        val rawOffset = position - center
        val length = sqrt(rawOffset.x * rawOffset.x + rawOffset.y * rawOffset.y)
        val boundedOffset = if (length > radius) rawOffset * (radius / length) else rawOffset
        thumbOffset = boundedOffset
        latestCallback(boundedOffset / radius)
    }

    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(label, style = MaterialTheme.typography.titleMedium)
        Canvas(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(1f)
                .onSizeChanged { layoutSize = it }
                .pointerInput(layoutSize) {
                    detectDragGestures(
                        onDragStart = { position -> updateThumb(position) },
                        onDragEnd = { updateThumb(null) },
                        onDragCancel = { updateThumb(null) },
                        onDrag = { change, _ -> updateThumb(change.position) },
                    )
                },
        ) {
            val center = Offset(size.width / 2f, size.height / 2f)
            val radius = size.minDimension * 0.34f
            drawCircle(colors.primary.copy(alpha = 0.12f), radius, center)
            drawCircle(colors.outline, radius, center, style = Stroke(width = 2.dp.toPx()))
            drawCircle(colors.primary, radius * 0.34f, center + thumbOffset)
        }
    }
}
