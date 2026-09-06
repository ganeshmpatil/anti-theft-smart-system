"""Core surveillance loop — orchestrates the full detection pipeline.

Alternates between two cameras, running motion detection then YOLO
inference on each frame. Publishes alerts via MQTT when intrusions
are confirmed.
"""

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone

import cv2

from .alert_manager import AlertManager
from .command_handler import CommandHandler
from .detection.exclusion_zones import ExclusionZoneFilter
from .detection.human_detector import HumanDetector
from .detection.motion_detector import MotionDetector
from .mqtt_client import MQTTClient
from .providers.interfaces import (
    ICameraProvider,
    IPowerProvider,
    ITamperProvider,
    IThermalProvider,
    IWatchdogProvider,
)
from .video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


class SurveillanceLoop:
    """Main surveillance loop that ties everything together."""

    def __init__(
        self,
        cam1: ICameraProvider,
        cam2: ICameraProvider,
        tamper: ITamperProvider,
        thermal: IThermalProvider,
        power: IPowerProvider,
        watchdog: IWatchdogProvider,
        detector: HumanDetector,
        mqtt_client: MQTTClient,
        alert_manager: AlertManager,
        command_handler: CommandHandler,
        exclusion_filter: ExclusionZoneFilter,
        config: dict,
    ):
        self._cam1 = cam1
        self._cam2 = cam2
        self._cameras = [cam1, cam2]
        self._tamper = tamper
        self._thermal = thermal
        self._power = power
        self._watchdog = watchdog
        self._detector = detector
        self._mqtt = mqtt_client
        self._alerts = alert_manager
        self._commands = command_handler
        self._exclusions = exclusion_filter
        self._config = config

        self._motion_detectors = {
            cam1.camera_id: MotionDetector(
                min_contour_area=config.get("detection", {}).get("min_motion_area", 3000)
            ),
            cam2.camera_id: MotionDetector(
                min_contour_area=config.get("detection", {}).get("min_motion_area", 3000)
            ),
        }

        self._video_recorder = VideoRecorder()
        self._pending_video_alert_payload: str | None = None

        self._running = False
        self._debug_window = config.get("simulation", {}).get("enable_debug_window", False)
        self._scan_count = 0
        self._last_heartbeat = 0
        self._heartbeat_interval = 60  # seconds
        self._start_time = time.monotonic()

        # Metrics
        self._inference_times: deque[float] = deque(maxlen=100)
        self._cycle_start = 0

    def run(self):
        """Main loop — runs until stopped or reboot requested."""
        self._running = True
        logger.info("Surveillance loop started")

        try:
            while self._running:
                # Check reboot request
                if self._commands.reboot_requested:
                    logger.warning("Reboot requested — exiting loop")
                    break

                # If disarmed, wait until re-armed
                if not self._commands.is_armed:
                    logger.info("System disarmed — waiting for arm command")
                    self._commands.wait_for_arm(timeout=5.0)
                    continue

                # Check schedule
                if not self._is_within_schedule():
                    time.sleep(30)
                    continue

                self._cycle_start = time.monotonic()

                # Check tamper
                if self._tamper.is_tampered():
                    self._handle_tamper()

                # Determine scan rate based on thermal and power state
                throttle = self._thermal.get_throttle_state()
                power_source = self._power.get_power_source()

                # Process each camera
                for camera in self._cameras:
                    if not self._running:
                        break

                    if not camera.is_alive():
                        logger.warning("Camera %s is not alive — attempting reconnect", camera.camera_id)
                        try:
                            camera.release()
                            if camera.open():
                                logger.info("Camera %s reconnected", camera.camera_id)
                            else:
                                logger.error("Camera %s reconnect failed — skipping", camera.camera_id)
                                continue
                        except Exception:
                            logger.exception("Camera %s reconnect error", camera.camera_id)
                            continue

                    self._process_camera(camera, throttle)

                # Ping watchdog
                self._watchdog.ping()

                # Send heartbeat periodically
                self._maybe_send_heartbeat()

                # Flush offline queue if connected
                self._flush_alert_queue()

                # Collect video clip if recording is done
                self._maybe_collect_video()

                # Handle on-demand snapshot
                if self._commands.snapshot_requested:
                    self._handle_snapshot_request()

                # Handle live feed
                if self._commands.live_feed_active:
                    self._handle_live_feed()

                # Scan cycle metrics
                self._scan_count += 1
                cycle_time = time.monotonic() - self._cycle_start

                # Log periodic status so we know the loop is alive
                if self._scan_count % 100 == 0:
                    logger.info("Loop alive: %d scans, %d alerts today, cycle=%.0fms",
                                self._scan_count, self._alerts.alerts_today,
                                cycle_time * 1000)

                # Throttle loop if needed
                if throttle == "critical":
                    time.sleep(5.0)
                elif throttle == "throttled" or power_source == "battery":
                    time.sleep(1.0)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt — stopping")
        finally:
            self._running = False
            self._cleanup()

    def stop(self):
        """Signal the loop to stop."""
        self._running = False

    def _process_camera(self, camera: ICameraProvider, throttle: str):
        """Run the detection pipeline on a single camera frame."""
        frame = camera.read_frame()
        if frame is None:
            return

        camera_id = camera.camera_id

        # Stage 1: Motion detection (~5ms)
        # In webcam/testing mode, skip motion gate so YOLO runs on every frame
        skip_motion_gate = self._config.get("mode") == "webcam"
        motion_detected, motion_area = self._motion_detectors[camera_id].detect(frame)

        if self._debug_window:
            self._show_debug(camera_id, frame, motion_detected, motion_area, [])

        if not motion_detected and not skip_motion_gate:
            return

        # Stage 2: YOLO inference — skip if thermal critical
        if throttle == "critical":
            logger.debug("Skipping YOLO — thermal critical")
            return

        t0 = time.monotonic()
        detections = self._detector.detect(frame)
        inference_ms = (time.monotonic() - t0) * 1000
        self._inference_times.append(inference_ms)

        # Apply exclusion zones
        detections = self._exclusions.filter(camera_id, detections)

        if self._debug_window:
            self._show_debug(camera_id, frame, motion_detected, motion_area, detections)

        # Push every frame to video recorder ring buffer
        self._video_recorder.push_frame(frame)

        if not detections:
            return

        # Stage 3: Alert manager (temporal filter + cooldown)
        device_status = self._get_device_status()
        alert = self._alerts.process_detections(
            camera_id, detections, frame, device_status
        )

        if alert is None:
            return

        # Publish alert (snapshot + metadata)
        payload = self._alerts.to_payload(alert)
        if self._mqtt.is_connected:
            success = self._mqtt.publish_alert(payload, alert.image_jpeg)
            if not success:
                self._alerts.queue_alert(alert)
        else:
            self._alerts.queue_alert(alert)

        # Trigger video recording (captures 5s pre + 5s post)
        if not self._video_recorder.is_recording():
            self._video_recorder.trigger()
            self._pending_video_alert_payload = payload

    def _handle_tamper(self):
        """Publish immediate tamper alert — queues if MQTT is offline."""
        logger.warning("TAMPER DETECTED — publishing alert")
        device_cfg = self._config.get("device", {})
        payload = json.dumps({
            "device_id": device_cfg.get("device_id", "unknown"),
            "farm_id": device_cfg.get("farm_id", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "tamper_detected",
            "device_status": self._get_device_status(),
        })
        if self._mqtt.is_connected:
            self._mqtt.publish_alert(payload, b"")
        else:
            logger.warning("MQTT offline — tamper alert queued for later delivery")
            self._alerts.queue_raw_payload(payload)

    def _handle_live_feed(self):
        """Stream JPEG frames via MQTT for the requested duration."""
        duration = self._commands.live_feed_duration
        fps = self._commands.live_feed_fps
        camera_id = self._commands.live_feed_camera
        frame_interval = 1.0 / fps

        # Pick the requested camera
        camera = self._cam1
        if camera_id == "cam_rear" and self._cam2.is_alive():
            camera = self._cam2
        elif not camera.is_alive():
            logger.error("Live feed camera not available")
            self._commands.stop_live_feed()
            return

        logger.info("Live feed started: %ds at %dfps from %s", duration, fps, camera.camera_id)
        start = time.monotonic()

        while self._commands.live_feed_active and self._running:
            if time.monotonic() - start >= duration:
                break

            frame_start = time.monotonic()
            frame = camera.read_frame()
            if frame is None:
                break

            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            self._mqtt.publish_live_frame(buf.tobytes())

            # Throttle to target FPS
            sleep_time = frame_interval - (time.monotonic() - frame_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

        self._commands.stop_live_feed()
        logger.info("Live feed ended after %.1fs", time.monotonic() - start)

    def _handle_snapshot_request(self):
        """Capture and publish a snapshot on demand."""
        for camera in self._cameras:
            if camera.is_alive():
                frame = camera.read_hires_frame()
                if frame is not None:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    self._mqtt.publish_alert(
                        json.dumps({"event_type": "snapshot_response", "camera_id": camera.camera_id}),
                        buf.tobytes(),
                    )
                    logger.info("Snapshot sent from %s", camera.camera_id)
                    break

    def _maybe_send_heartbeat(self):
        """Send heartbeat every N seconds."""
        now = time.monotonic()
        if (now - self._last_heartbeat) < self._heartbeat_interval:
            return

        self._last_heartbeat = now
        heartbeat = self._get_device_status()
        heartbeat.update({
            "uptime_seconds": int(now - self._start_time),
            "alerts_today": self._alerts.alerts_today,
            "alerts_queued": self._alerts.queue_size,
            "scan_count": self._scan_count,
            "firmware_version": "1.0.0",
            "model_version": "yolov5n-v1",
        })
        self._mqtt.publish_heartbeat(heartbeat)

    def _flush_alert_queue(self):
        """Flush offline queue if MQTT is connected. Re-queues on failure."""
        if not self._mqtt.is_connected or self._alerts.queue_size == 0:
            return

        queued = self._alerts.drain_queue()
        logger.info("Flushing %d queued alerts", len(queued))
        for alert in queued:
            if not self._mqtt.is_connected:
                # Connection dropped mid-flush — re-queue remaining
                self._alerts.queue_alert(alert)
                continue
            payload = self._alerts.to_payload(alert)
            success = self._mqtt.publish_alert(payload, alert.image_jpeg)
            if not success:
                self._alerts.queue_alert(alert)

    def _maybe_collect_video(self):
        """Collect and publish the video clip once post-event recording is done."""
        if not self._video_recorder.should_collect():
            return

        clip = self._video_recorder.collect()
        if clip is None:
            return

        logger.info("Video clip ready: %.1fs, %.1f KB",
                     clip.duration_seconds, len(clip.data) / 1024)

        if self._mqtt.is_connected:
            self._mqtt.publish_video(clip.data)
        else:
            logger.warning("MQTT offline — video clip discarded (too large to queue)")

        self._pending_video_alert_payload = None

    def _get_device_status(self) -> dict:
        """Build device status dict for heartbeats and alerts."""
        avg_inference = 0.0
        if self._inference_times:
            avg_inference = sum(self._inference_times) / len(self._inference_times)

        return {
            "device_id": self._config.get("device", {}).get("device_id", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_temp_c": self._thermal.get_cpu_temp(),
            "battery_pct": self._power.get_battery_pct(),
            "power_source": self._power.get_power_source(),
            "camera_1_status": "active" if self._cam1.is_alive() else "offline",
            "camera_2_status": "active" if self._cam2.is_alive() else "offline",
            "inference_avg_ms": round(avg_inference, 1),
        }

    def _is_within_schedule(self) -> bool:
        """Check if current time falls within the configured surveillance schedule."""
        schedule = self._config.get("schedule", {})
        if not schedule.get("enabled", False):
            return True  # no schedule = always active

        now = datetime.now()  # local time — farmers configure in their timezone
        start_hour = schedule.get("start_hour", 0)
        end_hour = schedule.get("end_hour", 24)

        if start_hour < end_hour:
            return start_hour <= now.hour < end_hour
        else:
            # Wraps midnight, e.g., 19:00 - 06:00
            return now.hour >= start_hour or now.hour < end_hour

    def _show_debug(self, camera_id: str, frame, motion: bool,
                    motion_area: int, detections: list):
        """Show debug window with detection overlays (simulation mode only)."""
        display = frame.copy()

        # Draw detections
        for det in detections:
            color = (0, 255, 0) if det.confidence >= 0.6 else (0, 255, 255)
            cv2.rectangle(display, (det.x, det.y),
                          (det.x + det.w, det.y + det.h), color, 2)
            label = f"person {det.confidence:.0%}"
            cv2.putText(display, label, (det.x, det.y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Draw exclusion zones
        zones = self._exclusions.get_zones(camera_id)
        for zone in zones:
            overlay = display.copy()
            cv2.rectangle(overlay, (zone.x, zone.y),
                          (zone.x + zone.w, zone.y + zone.h), (128, 128, 128), -1)
            cv2.addWeighted(overlay, 0.3, display, 0.7, 0, display)

        # Status bar
        status = f"{camera_id} | Motion: {'YES' if motion else 'NO'} ({motion_area})"
        status += f" | Persons: {len(detections)}"
        status += f" | {'ARMED' if self._commands.is_armed else 'DISARMED'}"
        cv2.putText(display, status, (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        window_name = f"ATSS Debug - {camera_id}"
        cv2.imshow(window_name, display)
        key = cv2.waitKey(1) & 0xFF

        # Keyboard controls
        if key == ord("q"):
            self.stop()
        elif key == ord("d"):
            if self._commands.is_armed:
                self._commands.handle("disarm", {})
            else:
                self._commands.handle("arm", {})
        elif key == ord("t"):
            self._tamper.trigger_tamper() if hasattr(self._tamper, "trigger_tamper") else None

    def _cleanup(self):
        """Release resources."""
        logger.info("Cleaning up surveillance loop")
        if self._debug_window:
            cv2.destroyAllWindows()
