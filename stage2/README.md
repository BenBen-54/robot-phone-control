# Stage 2 Autonomous Mission

Stage two is isolated from the stable stage-one release tagged
`stage1-stable-v1.0.0`.

The target mission is:

```text
find pillar -> approach pillar -> orbit pillar -> find task card
-> OCR task -> find gong -> approach gong -> execute action
```

## Safety rules

- Stage-one and stage-two services must never run at the same time.
- Stage two starts in dry-run mode until detection and control are validated.
- No stage-two script may overwrite the robot action file or UART bridge firmware.
- Losing a required visual target stops the chassis before recovery begins.
- Every state has a timeout that leads to `FAILSAFE`.

## Current milestone

The first milestone contains:

- a pure Python mission state machine;
- visual-servo command calculations;
- offline unit tests;
- an Atlas environment inspection script;
- a camera dataset collection tool.

It does not yet contain a trained YOLO model and does not send real robot commands.
