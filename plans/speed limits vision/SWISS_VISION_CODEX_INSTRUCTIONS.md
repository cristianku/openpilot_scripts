# Swiss Vision Speed Limit for openpilot / sunnypilot + Chestnut

## Mission

Build a Switzerland-focused traffic-sign vision subsystem for openpilot/sunnypilot.

The first target is reliable recognition of Swiss speed-limit signs from the road camera and publication of a stable `VisionSpeedLimit` signal.

Training will run on an NVIDIA Tesla V100.

Production inference will run in the vehicle on the external AMD GPU connected through comma Chestnut.

The first implementation MUST run in **shadow mode only**:
- detect signs;
- classify speed limits;
- track detections temporally;
- log predictions and confidence;
- display/debug results;
- do NOT alter cruise speed;
- do NOT send control commands to the vehicle.

Only after offline validation and extensive on-road shadow-mode validation should integration with sunnypilot Speed Limit Assist be considered.

---

# 1. Current platform constraints

Treat these as architectural constraints unless inspection of the current repository proves otherwise.

## Chestnut

Current openpilot supports large-model execution on an external GPU through Chestnut.

In current openpilot source:

- `modeld.py` explicitly states that only `modeld` can access Chestnut.
- Chestnut uses the tinygrad external AMD path.
- build/runtime configuration uses a `USB+AMD` tinygrad device.
- the normal openpilot model can fall back to the local model if the Chestnut model fails.

Therefore:

**DO NOT design the production system around a standalone Python/ROCm/ONNX service directly owning the Chestnut GPU.**

Prefer:

```text
camerad
   |
   v
VisionIPC
   |
   v
modeld
   |
   +---- openpilot driving model
   |
   +---- Swiss traffic-sign model
                |
                v
        temporal filtering
                |
                v
        VisionSpeedLimit
```

The custom sign model should reuse the camera frames already available through `VisionIPC`.

Avoid copying full-resolution frames unnecessarily between processes.

---

# 2. Target architecture

Separate training architecture from vehicle inference architecture.

## Training

```text
Swiss road recordings / extracted frames
              |
              v
       annotation pipeline
              |
              v
       PyTorch training
              |
              v
        Tesla V100
              |
              v
       validated weights
              |
              v
       export / compile
```

## Vehicle

```text
comma camera
     |
     v
  camerad
     |
     v
 VisionIPC
     |
     v
   modeld
     |
     +--------------------------+
     |                          |
     v                          v
openpilot model         SwissSignDetector
                                |
                                v
                         SignClassifier
                                |
                                v
                        TemporalTracker
                                |
                                v
                        VisionSpeedLimit
                                |
                    shadow-mode logger/HUD
```

Do not connect this output to longitudinal actuation during the first phases.

---

# 3. Initial recognition scope

Version 1 should focus on speed-related Swiss signs.

Recognize at minimum:

```text
20
30
40
50
60
70
80
100
120
```

Also create explicit classes for:

```text
end_speed_limit
end_all_restrictions
unknown_speed_sign
```

Design the class system so later versions can support:

- temporary construction limits;
- variable/electronic signs;
- motorway / expressway context;
- town-entry / town-exit context;
- supplementary plates;
- rain/time-dependent restrictions;
- lane-specific restrictions;
- school-zone signs;
- signs applying to adjacent ramps or parallel roads.

Do not silently map uncertain signs to a numeric speed.

---

# 4. Detection strategy

Start with a two-stage design unless benchmarks prove a single-stage model is clearly superior.

```text
full camera frame
      |
      v
traffic-sign detector
      |
      v
bounding-box crops
      |
      v
speed-sign classifier
```

Reasons:

- speed signs may occupy very few pixels in the original frame;
- classification can operate on a higher-resolution crop;
- detector and classifier can be improved independently;
- false-positive analysis is easier.

The detector should identify candidate traffic signs.

The classifier should identify the speed class from the crop.

Keep model interfaces modular.

Example internal data type:

```python
@dataclass
class SignDetection:
    bbox: tuple[float, float, float, float]
    detector_confidence: float
    sign_type: str
    value_kph: int | None
    classifier_confidence: float
    frame_id: int
    timestamp_ns: int
```

---

# 5. Temporal filtering

Never change the accepted speed limit because of a single frame.

Implement a temporal tracker.

Concept:

```text
frame N      -> 80 @ 0.91
frame N+1    -> 80 @ 0.96
frame N+2    -> 80 @ 0.95
frame N+3    -> 80 @ 0.97

track confidence rises
        |
        v
accepted candidate = 80
```

Use a state machine rather than only averaging probabilities.

Suggested states:

```text
NONE
CANDIDATE
CONFIRMED
STALE
REJECTED
```

Candidate confirmation should consider:

- number of observations;
- confidence;
- temporal consistency;
- bounding-box trajectory;
- size increase as vehicle approaches sign;
- spatial location;
- detection age.

Configuration values must be tunable, not hard-coded throughout the implementation.

Example:

```python
MIN_CONFIRMATIONS = 3
MIN_CLASS_CONFIDENCE = 0.85
MAX_TRACK_GAP_MS = 500
CONFIRMED_TTL_MS = 3000
```

These are starting values only.

---

# 6. Prevent wrong-road / wrong-lane signs

A major failure mode is detecting a valid sign that does not apply to the ego vehicle.

The architecture must preserve enough metadata to later reject:

- signs facing the opposite direction;
- signs belonging to parallel roads;
- signs on exit ramps;
- signs applying only to another lane;
- signs visible far outside the ego-road corridor.

Version 1 can use heuristics.

Potential signals:

```text
bounding-box position
bounding-box motion
camera calibration
road vanishing point
openpilot path prediction
lane/path geometry
vehicle yaw
sign scale change over time
```

Do not assume that the closest detected speed sign necessarily applies to the ego vehicle.

Build the API so an `applicability_score` can be added without changing the detector interface.

---

# 7. Dataset design

Create a reproducible dataset pipeline.

Recommended layout:

```text
dataset/
  raw/
  frames/
  annotations/
  splits/
  metadata/
```

Each sample should preserve metadata when available:

```json
{
  "route_id": "...",
  "frame_id": 123456,
  "timestamp_ns": 0,
  "vehicle_speed_mps": 21.4,
  "gps_lat": null,
  "gps_lon": null,
  "car_speed_limit_kph": 80,
  "osm_speed_limit_kph": 80,
  "weather": null,
  "day_night": null
}
```

GPS must NOT be required for the vision model itself.

It is metadata for analysis and dataset management.

---

# 8. Pseudo-label sources

Where legally and technically available, use weak labels to accelerate dataset construction.

Potential sources:

```text
Peugeot factory TSR / CAN value
OSM speed limit
manual annotation
existing traffic-sign datasets
model-assisted annotation
```

Treat Peugeot/OSM values as **pseudo-labels**, not ground truth.

Example:

```text
vision crop detected near road sign
Peugeot TSR changes 120 -> 80
OSM = 80
candidate label = 80
```

This sample can be queued for human verification.

Never automatically trust every pseudo-label.

---

# 9. Dataset split rules

Avoid random-frame leakage.

Frames from the same drive or same physical sign must not appear in both training and validation sets.

Split by:

```text
route
date
location cluster
```

Preferred:

```text
train: 70-80%
validation: 10-15%
test: 10-15%
```

Maintain a dedicated Swiss holdout test set that is never used for tuning.

Create additional challenge sets:

```text
night
rain
snow
sun glare
construction
small distant signs
partial occlusion
electronic signs
urban clutter
motorway
```

---

# 10. Training hardware

Primary training GPU:

```text
NVIDIA Tesla V100
```

Use PyTorch with CUDA.

Enable:

```python
torch.backends.cudnn.benchmark = True
```

Use mixed precision where supported.

The V100 has Tensor Cores optimized for FP16, so test AMP training.

Example:

```python
with torch.autocast(device_type="cuda", dtype=torch.float16):
    loss = model(images, targets)
```

Prefer gradient accumulation rather than reducing input resolution too aggressively.

Training scripts must support configurable:

```text
batch size
input resolution
learning rate
workers
epochs
gradient accumulation
AMP on/off
checkpoint path
resume
```

Do not assume a fixed V100 VRAM size in code.

Detect available VRAM and report it at startup.

---

# 11. Training performance priorities

Traffic signs are small objects.

Do not optimize only for generic object-detection mAP.

Track:

```text
mAP50
mAP50-95
precision
recall
false positives / km
false negatives / km
classification confusion matrix
distance-to-first-detection
stable-confirmation distance
```

The most important real-world metric is approximately:

```text
correct stable speed-limit recognition
before the vehicle reaches the sign
with extremely low false-positive rate
```

False positives are more dangerous than slightly late detections.

---

# 12. Image resolution

Do not immediately resize everything to 640x640.

Benchmark multiple resolutions.

Candidate detector resolutions:

```text
640
960
1280
```

Traffic signs at distance may require higher resolution.

Also investigate region-of-interest processing.

For example:

```text
full road frame
      |
      +--> likely roadside ROI
      |
      +--> overhead-sign ROI
```

Measure accuracy versus inference cost.

---

# 13. Data augmentation

Use realistic augmentation.

Useful:

```text
brightness
contrast
motion blur
defocus blur
light rain
fog
JPEG compression
small rotations
perspective variation
partial occlusion
sun glare simulation
```

Avoid transformations that create unrealistic Swiss signs.

Do not horizontally mirror signs if that produces unrealistic road geometry or sign placement.

---

# 14. Production inference target

The production target is:

```text
comma device + Chestnut + external AMD GPU
```

Training uses PyTorch/CUDA.

Deployment does NOT need to use the same runtime.

Keep the neural-network architecture exportable.

Avoid unsupported custom PyTorch operators.

Preferred path:

```text
PyTorch model
      |
      v
export/intermediate representation
      |
      v
tinygrad-compatible compilation/runtime
      |
      v
Chestnut AMD GPU
```

Before selecting a final architecture, create a deployment proof-of-concept with a very small model.

The first milestone is not accuracy.

The first milestone is:

```text
camera frame
   ->
custom model executes on Chestnut GPU
   ->
known deterministic output
```

Only then scale model complexity.

---

# 15. Chestnut integration rules

Inspect current openpilot/sunnypilot source before implementation.

Relevant areas include:

```text
openpilot/selfdrive/modeld/
camerad
VisionIPC
tinygrad model compilation
Chestnut detection
USB+AMD device configuration
```

Current openpilot source contains an explicit constraint that only `modeld` accesses Chestnut.

Therefore initially implement custom inference within the `modeld` ownership boundary.

Do NOT create competing processes that both try to acquire the external GPU.

If architectural changes are needed:

1. document them;
2. prove Chestnut locking/lifetime behavior;
3. benchmark latency;
4. preserve fallback behavior;
5. avoid destabilizing the driving model.

The sign model MUST NOT delay the main driving model.

If necessary:

```text
driving model = highest priority
sign model    = opportunistic / lower frequency
```

---

# 16. Inference frequency

The sign detector probably does not need to run at camera FPS.

Start testing around:

```text
detector: 10 Hz
classifier: per tracked candidate
tracker: camera/model update rate
```

The tracker should preserve objects between detector runs.

Possible optimization:

```text
Frame 0 -> detector
Frame 1 -> tracker
Frame 2 -> tracker
Frame 3 -> detector
```

Benchmark instead of assuming.

---

# 17. Latency budget

Record timing for every stage.

Example telemetry:

```text
frame capture timestamp
frame available timestamp
preprocess ms
detector ms
classifier ms
tracking ms
total vision latency ms
```

Initial target:

```text
sign-model inference should not interfere with openpilot's primary model deadline.
```

Do not enforce an arbitrary FPS without measuring the actual Chestnut workload.

---

# 18. Output API

Define a clean internal message.

Suggested conceptual schema:

```text
VisionSpeedLimit
  speedKph
  confidence
  source
  signType
  frameId
  timestamp
  age
  bbox
  confirmed
  applicabilityScore
```

Example:

```python
VisionSpeedLimit(
    speed_kph=80,
    confidence=0.97,
    source="vision",
    sign_type="speed_limit",
    frame_id=12345,
    confirmed=True,
)
```

Use cereal/capnp conventions if integrating into openpilot messaging.

Do not reuse unrelated fields as a shortcut.

---

# 19. Shadow mode

This is mandatory for the first production implementation.

Log:

```text
timestamp
frame id
vision prediction
vision confidence
Peugeot TSR
OSM limit
current sunnypilot selected limit
vehicle speed
bounding box
track id
```

Example debug line:

```text
VISION=80(0.97) CAR=80 MAP=80 SELECTED=80 TRACK=31
```

Mismatch example:

```text
VISION=60(0.94) CAR=80 MAP=80 SELECTED=80 TRACK=108 MISMATCH
```

Never change cruise speed in shadow mode.

---

# 20. Offline replay

Before road testing, support replay of recorded routes.

The same inference code should be executable against saved frames/routes.

Create tooling that can generate:

```text
prediction timeline
confidence timeline
detected sign thumbnails
false-positive gallery
false-negative gallery
confusion matrix
per-route statistics
```

A developer must be able to inspect every accepted speed transition.

---

# 21. Safety gates

Do not connect vision output to Speed Limit Assist until all of the following exist:

```text
offline validation
route replay
shadow mode
confidence threshold
temporal confirmation
stale-data handling
model-failure handling
Chestnut-failure handling
manual disable switch
structured logging
```

Fallback must be safe.

If the sign model crashes:

```text
no VisionSpeedLimit
```

Never:

```text
speed limit = 0
speed limit = previous value forever
arbitrary default speed
```

---

# 22. sunnypilot integration

Current sunnypilot Speed Limit Assist supports speed-limit information from:

```text
Car State
Map Data
```

The future goal is to add:

```text
Vision
```

Conceptually:

```text
Car State
Map Data
Vision
    |
    v
Speed Limit Policy
    |
    v
SLA
```

Do not modify SLA policy behavior until the Vision source is proven.

Possible future policies:

```text
Vision Only
Vision Priority
Car State Priority
Map Priority
Vision + Car agreement
Majority agreement
Conservative minimum
```

These policies are later milestones.

---

# 23. Model versioning

Every model must have immutable metadata.

Example:

```json
{
  "model_name": "swiss-speed-sign",
  "version": "0.1.0",
  "git_commit": "...",
  "dataset_version": "ch-v1",
  "input_size": [1280, 720],
  "trained_on": "Tesla V100",
  "date": "YYYY-MM-DD"
}
```

Include model version in runtime logs.

---

# 24. Reproducibility

Training must be reproducible from repository scripts.

Provide:

```text
requirements / environment
dataset preparation command
training command
validation command
export command
Chestnut compile command
replay command
```

Example desired UX:

```bash
python tools/prepare_dataset.py --config configs/swiss_v1.yaml

python train.py \
  --config configs/swiss_v1.yaml \
  --device cuda

python validate.py \
  --checkpoint runs/swiss_v1/best.pt

python export.py \
  --checkpoint runs/swiss_v1/best.pt
```

Do not hide critical training settings inside notebooks.

Notebooks may be used for exploration only.

---

# 25. Repository structure

Prefer approximately:

```text
swiss_vision/
  README.md
  configs/
  datasets/
  models/
  training/
  inference/
  tracking/
  evaluation/
  tools/
  tests/
  openpilot/
```

Possible content:

```text
models/
  detector.py
  classifier.py

training/
  train_detector.py
  train_classifier.py

inference/
  pipeline.py
  preprocess.py
  postprocess.py

tracking/
  sign_tracker.py

evaluation/
  metrics.py
  route_evaluator.py

openpilot/
  messages.py
  chestnut_runner.py
```

Do not create unnecessary abstractions before the first end-to-end prototype works.

---

# 26. Tests

Write tests for non-neural logic.

Mandatory unit tests:

```text
temporal confirmation
confidence threshold
track timeout
stale prediction handling
speed transition handling
unknown class
model exception
empty detections
duplicate signs
```

Integration tests should verify:

```text
frame -> detector -> classifier -> tracker -> VisionSpeedLimit
```

Include a deterministic tiny test model or mocked inference backend.

---

# 27. Development sequence

Follow these milestones in order.

## Milestone 0 — Inspect current platform

Study current:

```text
openpilot master
sunnypilot branch actually installed
Chestnut implementation
modeld
VisionIPC
tinygrad compile path
Speed Limit Assist
```

Produce:

```text
docs/platform-analysis.md
```

Do not code the final architecture before this inspection.

---

## Milestone 1 — Chestnut proof of concept

Goal:

```text
camera frame
   ->
trivial custom neural network
   ->
Chestnut AMD GPU
   ->
logged result
```

Requirements:

- no vehicle control;
- no modification of driving-model outputs;
- benchmark inference time;
- prove driving model remains stable.

---

## Milestone 2 — Dataset tooling

Implement:

```text
route/frame extractor
annotation format
dataset splitter
metadata collector
pseudo-label importer
```

No major training work before dataset versioning exists.

---

## Milestone 3 — Baseline detector

Train a baseline model on Tesla V100.

Goal:

```text
detect traffic-sign bounding boxes
```

Measure small-sign recall.

---

## Milestone 4 — Speed classifier

Train:

```text
20/30/40/50/60/70/80/100/120/end/unknown
```

Generate confusion matrix.

---

## Milestone 5 — Temporal tracker

Combine detections across frames.

Output confirmed speed transitions.

---

## Milestone 6 — Offline route replay

Replay Swiss road footage.

Generate error reports and visual galleries.

---

## Milestone 7 — Vehicle shadow mode

Run on Chestnut.

Display/log predictions.

Do not control speed.

Collect large-scale real-world performance data.

---

## Milestone 8 — SLA experimental source

Only after validation, expose Vision as an experimental sunnypilot Speed Limit source.

Default must remain disabled.

---

# 28. Codex working rules

When modifying openpilot/sunnypilot:

1. Inspect existing architecture first.
2. Make the smallest coherent change.
3. Preserve upstream style.
4. Do not duplicate existing camera or GPU pipelines.
5. Do not bypass safety abstractions.
6. Do not modify CAN actuation for this project.
7. Keep the first implementation shadow-only.
8. Add logging before optimizing.
9. Benchmark every change touching `modeld`.
10. Add tests for non-neural logic.
11. Document all deviations from upstream.
12. Never claim a model works on Chestnut until tested on the actual Chestnut hardware.
13. Never claim a speed-sign transition is safe enough for control based only on validation-set accuracy.

---

# 29. Performance philosophy

Priority order:

```text
1. do not interfere with primary driving inference
2. false-positive avoidance
3. stable temporal behavior
4. detection distance
5. recall
6. raw FPS
```

A detector running at 10 Hz with robust tracking is preferable to a 30 Hz detector that steals compute from the primary driving model.

---

# 30. First task for Codex

Start by performing **Milestone 0 only**.

Inspect the current source tree and answer:

1. Exactly how does current `modeld` acquire and use Chestnut?
2. Which tinygrad device owns the external AMD GPU?
3. How is the big model compiled and loaded?
4. Can two model JITs share the same Chestnut device within `modeld`?
5. What is the least invasive place to execute a second model?
6. How can road-camera frames be reused without an additional full-frame copy?
7. What scheduling mechanism can guarantee the sign model never delays the primary driving model?
8. Where should a new `VisionSpeedLimit` cereal message live?
9. Where does current sunnypilot Speed Limit Assist consume Car State and Map Data?
10. What files would need modification to add a disabled-by-default Vision source?

Produce:

```text
docs/platform-analysis.md
```

with:

```text
current architecture
relevant files/functions
proposed integration
risks
unknowns
benchmark plan
minimal Milestone-1 patch plan
```

Do not implement vehicle actuation.

---

# 31. Definition of success for V1

V1 is successful when:

```text
Swiss speed signs are recognized reliably from the comma road camera,
using a model trained on the Tesla V100,
executed on the Chestnut external AMD GPU,
without disturbing openpilot driving-model timing,
and predictions can be replayed, inspected and validated in shadow mode.
```

The V1 deliverable is NOT automatic speed control.

The V1 deliverable is a trustworthy vision speed-limit source.
