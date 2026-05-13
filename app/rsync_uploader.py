import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RsyncResult:
    success: bool
    stderr: str = ""


class RsyncUploader:
    def __init__(self, host: str, user: str, port: int, dest: str, ssh_key: str):
        self.host = host
        self.user = user
        self.port = port
        self.dest = dest
        self.ssh_key = ssh_key

    def upload(self, files: list[Path]) -> RsyncResult:
        if not files:
            return RsyncResult(True)
        ssh_cmd = f"ssh -i {self.ssh_key} -p {self.port} -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
        cmd = [
            "rsync", "-az", "--checksum",
            "-e", ssh_cmd,
            *[str(f) for f in files],
            f"{self.user}@{self.host}:{self.dest}",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return RsyncResult(False, "rsync timeout (300s)")
        except FileNotFoundError:
            return RsyncResult(False, "rsync binary not found")
        if r.returncode != 0:
            logging.error(f"rsync exited {r.returncode}: {r.stderr}")
            return RsyncResult(False, r.stderr.strip())
        return RsyncResult(True)
