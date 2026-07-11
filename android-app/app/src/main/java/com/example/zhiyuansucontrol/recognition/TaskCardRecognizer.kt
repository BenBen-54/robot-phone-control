package com.example.zhiyuansucontrol.recognition

import android.content.Context
import android.net.Uri
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions

enum class TaskCard(
    val phrase: String,
    val actionId: Int,
) {
    // Action slots 1 and 2 are configured in the official action editor.
    // The UDP protocol addresses them as action_id 0 and 1 respectively.
    POSITION_ONE_CHOP("位置1 劈砍", 0),
    POSITION_TWO_CHOP("位置2 劈砍", 1),
}

data class TaskRecognitionResult(
    val task: TaskCard?,
    val rawText: String,
)

/** Recognizes only the two printed task-card phrases used in phase one. */
class TaskCardRecognizer {
    private val recognizer = TextRecognition.getClient(
        ChineseTextRecognizerOptions.Builder().build(),
    )

    fun recognize(
        context: Context,
        photoUri: Uri,
        onSuccess: (TaskRecognitionResult) -> Unit,
        onFailure: (Exception) -> Unit,
    ) {
        val image = try {
            InputImage.fromFilePath(context, photoUri)
        } catch (error: Exception) {
            onFailure(error)
            return
        }

        recognizer.process(image)
            .addOnSuccessListener { result ->
                val rawText = result.text
                onSuccess(TaskRecognitionResult(findTask(rawText), rawText))
            }
            .addOnFailureListener(onFailure)
    }

    fun close() {
        recognizer.close()
    }

    private fun findTask(rawText: String): TaskCard? {
        val normalized = rawText.replace(Regex("\\s+"), "")
        val hasChop = normalized.contains("劈砍") ||
            (normalized.contains('劈') && (normalized.contains('砍') || normalized.contains('坎')))
        if (!hasChop) {
            return null
        }

        return when {
            normalized.contains("位置1") || normalized.contains("位置一") || normalized.contains("位置I") -> {
                TaskCard.POSITION_ONE_CHOP
            }
            normalized.contains("位置2") || normalized.contains("位置二") -> {
                TaskCard.POSITION_TWO_CHOP
            }
            else -> null
        }
    }
}
