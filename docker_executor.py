import os
import logging
import docker
from docker.errors import ContainerError, NotFound, APIError

logger = logging.getLogger(__name__)


class DockerExecutor:
    def __init__(
        self,
        image: str,
        workspace_dir: str,
        mem_limit: str = "512m",
        timeout: int = 30,
        idle_timeout: int = 300,
    ):
        self._client = docker.from_env()
        self._image = image
        self._workspace_dir = os.path.abspath(workspace_dir)
        self._mem_limit = mem_limit
        self._timeout = timeout
        self._idle_timeout = idle_timeout
        self._container = None

        os.makedirs(self._workspace_dir, exist_ok=True)

    def _ensure_container(self):
        """Start or reuse the session container."""
        if self._container is not None:
            try:
                self._container.reload()
                if self._container.status == "running":
                    return
            except (NotFound, APIError):
                self._container = None

        logger.info("Starting new session container")
        self._container = self._client.containers.run(
            self._image,
            command="sleep infinity",
            detach=True,
            user="1000:1000",
            read_only=True,
            network_disabled=True,
            mem_limit=self._mem_limit,
            cpu_period=100000,
            cpu_quota=50000,
            security_opt=["no-new-privileges"],
            cap_drop=["ALL"],
            volumes={
                self._workspace_dir: {
                    "bind": "/workspace",
                    "mode": "rw,nosuid,nodev",
                }
            },
            tmpfs={"/tmp": "size=100M"},
            working_dir="/workspace",
        )

    def _validate_path(self, path: str) -> str:
        """Validate path is within /workspace. Returns the path."""
        resolved = os.path.realpath(os.path.normpath(path))
        if not resolved.startswith("/workspace"):
            raise ValueError(f"path traversal blocked: {path}")
        return resolved

    def run_command(self, command: str) -> dict:
        """Execute a command in the session container."""
        self._ensure_container()
        try:
            exec_result = self._container.exec_run(
                ["bash", "-c", command],
                workdir="/workspace",
                user="1000:1000",
                demux=True,
                timeout=self._timeout,
            )
            stdout = exec_result.output[0] or b""
            stderr = exec_result.output[1] or b""
            output = (stdout + stderr).decode("utf-8", errors="replace")
            return {
                "exit_code": exec_result.exit_code,
                "output": output,
            }
        except Exception as e:
            if "timeout" in str(e).lower() or "read timed out" in str(e).lower():
                return {
                    "exit_code": -1,
                    "output": f"Timeout: command exceeded {self._timeout}s limit",
                }
            return {
                "exit_code": -1,
                "output": f"Error: {str(e)}",
            }

    def read_file(self, path: str) -> str:
        """Read a file from the workspace via container."""
        self._validate_path(path)
        self._ensure_container()
        result = self.run_command(f"cat '{path}'")
        if result["exit_code"] != 0:
            if "No such file" in result["output"]:
                raise FileNotFoundError(f"File not found: {path}")
            raise RuntimeError(result["output"])
        return result["output"]

    def write_file(self, path: str, content: str) -> None:
        """Write a file to the workspace via container."""
        self._validate_path(path)
        self._ensure_container()
        import base64
        b64 = base64.b64encode(content.encode()).decode()
        result = self.run_command(
            f"mkdir -p $(dirname '{path}') && echo '{b64}' | base64 -d > '{path}'"
        )
        if result["exit_code"] != 0:
            raise RuntimeError(f"Failed to write file: {result['output']}")

    def list_files(self, path: str) -> str:
        """List directory contents via container."""
        self._validate_path(path)
        self._ensure_container()
        result = self.run_command(f"ls -la '{path}'")
        if result["exit_code"] != 0:
            raise RuntimeError(result["output"])
        return result["output"]

    def cleanup(self):
        """Stop and remove the session container."""
        if self._container is not None:
            try:
                self._container.stop(timeout=5)
                self._container.remove(force=True)
            except (NotFound, APIError):
                pass
            self._container = None
            logger.info("Session container cleaned up")

    def is_available(self) -> bool:
        """Check if Docker daemon is reachable."""
        try:
            self._client.ping()
            return True
        except Exception:
            return False
