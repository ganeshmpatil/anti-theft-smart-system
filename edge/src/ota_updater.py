"""OTA (Over-The-Air) updater for edge devices.

Receives update commands via MQTT, downloads the update tarball,
verifies its SHA-256 checksum, extracts it, and restarts the service.

Update tarball structure (tar.gz):
    edge/
      src/
      models/
      config/
      requirements.txt

The updater:
1. Downloads to a temp directory
2. Verifies SHA-256 checksum
3. Extracts to /opt/surveillance (overwrites src/, models/)
4. Installs new requirements if requirements.txt changed
5. Restarts the systemd service
"""

import hashlib
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import threading
from pathlib import Path
from urllib.request import urlretrieve

logger = logging.getLogger(__name__)

INSTALL_DIR = Path("/opt/surveillance")
SERVICE_NAME = "atss-surveillance"
PIP = INSTALL_DIR / "venv" / "bin" / "pip"


class OTAUpdater:
    """Handles OTA firmware updates triggered via MQTT commands."""

    def __init__(self, current_version: str = "0.0.0"):
        self.current_version = current_version
        self._updating = threading.Lock()

    def handle_update_command(self, params: dict):
        """Called by CommandHandler when an 'ota_update' action is received.

        Expected params:
            url: str       — download URL for the tar.gz
            sha256: str    — expected SHA-256 hex digest
            version: str   — new version string
        """
        url = params.get("url", "")
        expected_sha = params.get("sha256", "")
        new_version = params.get("version", "")

        if not url or not expected_sha:
            logger.error("OTA update missing url or sha256")
            return False

        if new_version and new_version == self.current_version:
            logger.info("OTA: already on version %s — skipping", new_version)
            return False

        # Run update in a background thread to not block the surveillance loop
        thread = threading.Thread(
            target=self._do_update,
            args=(url, expected_sha, new_version),
            daemon=True,
        )
        thread.start()
        return True

    def _do_update(self, url: str, expected_sha: str, new_version: str):
        if not self._updating.acquire(blocking=False):
            logger.warning("OTA: update already in progress")
            return

        try:
            logger.info("OTA: starting update to version %s", new_version)
            logger.info("OTA: downloading %s", url)

            # Download
            tmpdir = tempfile.mkdtemp(prefix="atss_ota_")
            tarball_path = os.path.join(tmpdir, "update.tar.gz")
            try:
                urlretrieve(url, tarball_path)
            except Exception:
                logger.exception("OTA: download failed")
                shutil.rmtree(tmpdir, ignore_errors=True)
                return

            # Verify checksum
            actual_sha = self._sha256(tarball_path)
            if actual_sha != expected_sha.lower():
                logger.error("OTA: checksum mismatch! expected=%s actual=%s",
                             expected_sha, actual_sha)
                shutil.rmtree(tmpdir, ignore_errors=True)
                return

            logger.info("OTA: checksum verified")

            # Extract
            extract_dir = os.path.join(tmpdir, "extracted")
            os.makedirs(extract_dir)
            try:
                with tarfile.open(tarball_path, "r:gz") as tar:
                    # Security: reject paths that escape the extract dir
                    for member in tar.getmembers():
                        if member.name.startswith("/") or ".." in member.name:
                            logger.error("OTA: tarball contains unsafe path: %s", member.name)
                            shutil.rmtree(tmpdir, ignore_errors=True)
                            return
                    tar.extractall(path=extract_dir)
            except tarfile.TarError:
                logger.exception("OTA: failed to extract tarball")
                shutil.rmtree(tmpdir, ignore_errors=True)
                return

            # Find the edge directory in the extracted content
            edge_dir = self._find_edge_dir(extract_dir)
            if not edge_dir:
                logger.error("OTA: no 'edge/' or 'src/' directory found in tarball")
                shutil.rmtree(tmpdir, ignore_errors=True)
                return

            # Copy updated files to install directory
            self._apply_update(edge_dir)

            # Install new requirements if changed
            new_reqs = os.path.join(edge_dir, "requirements.txt")
            if os.path.exists(new_reqs) and PIP.exists():
                logger.info("OTA: installing updated requirements")
                subprocess.run(
                    [str(PIP), "install", "-r", new_reqs, "--quiet"],
                    timeout=300,
                )

            # Write version file
            version_file = INSTALL_DIR / "VERSION"
            version_file.write_text(new_version)
            logger.info("OTA: update applied — version %s", new_version)

            # Cleanup temp files
            shutil.rmtree(tmpdir, ignore_errors=True)

            # Restart service
            logger.info("OTA: restarting service %s", SERVICE_NAME)
            subprocess.run(["systemctl", "restart", SERVICE_NAME], timeout=30)

        except Exception:
            logger.exception("OTA: unexpected error during update")
        finally:
            self._updating.release()

    def _sha256(self, filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _find_edge_dir(self, extract_dir: str) -> str | None:
        """Find the edge source directory in the extracted tarball."""
        # Could be edge/ at root or directly contain src/
        for root, dirs, files in os.walk(extract_dir):
            if "src" in dirs:
                return root
            if root.endswith("/edge") or root.endswith("\\edge"):
                return root
        return None

    def _apply_update(self, source_dir: str):
        """Copy updated directories from source to install dir."""
        updatable = ["src", "models"]
        for dirname in updatable:
            src = Path(source_dir) / dirname
            dst = INSTALL_DIR / dirname
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                logger.info("OTA: updated %s/", dirname)
