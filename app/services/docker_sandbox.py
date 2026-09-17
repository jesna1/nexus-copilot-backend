import docker
import os
import tempfile

class DockerSandbox:
    def __init__(self, image: str = "python:3.11-slim"):
        self.client = docker.from_env()
        self.image = image

    def run_python_code(self, code: str, timeout: int = 10) -> dict:
        """Runs Python code inside an isolated Docker container with strict timeout handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            container = None
            try:
                # Start container detached to manage process lifecycle and timeout
                container = self.client.containers.run(
                    image=self.image,
                    command="python /app/script.py",
                    volumes={temp_dir: {"bind": "/app", "mode": "ro"}},
                    network_mode="none",  # Block network access
                    mem_limit="128m",     # Memory cap
                    nano_cpus=1000000000, # 1 CPU core cap
                    detach=True,
                    stdout=True,
                    stderr=True,
                )

                # Wait for container execution with explicit timeout
                result = container.wait(timeout=timeout)
                logs = container.logs(stdout=True, stderr=True).decode("utf-8")
                container.remove()

                exit_code = result.get("StatusCode", 0)
                if exit_code == 0:
                    return {
                        "success": True,
                        "output": logs,
                        "error": None
                    }
                else:
                    return {
                        "success": False,
                        "output": logs,
                        "error": f"Execution Error (Exit Code {exit_code}): {logs}"
                    }

            except Exception as e:
                # Force kill container if execution times out or raises an exception
                if container:
                    try:
                        container.kill()
                        container.remove()
                    except Exception:
                        pass

                return {
                    "success": False,
                    "output": "",
                    "error": f"Sandbox Exception: {str(e)}"
                }

docker_sandbox = DockerSandbox()