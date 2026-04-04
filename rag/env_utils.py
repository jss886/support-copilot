import os
import subprocess


def _read_windows_env_var(name: str) -> str | None:
    for scope in ("User", "Machine"):
        command = f"[Environment]::GetEnvironmentVariable('{name}', '{scope}')"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=10,
        )
        value = result.stdout.strip()
        if value:
            return value
    return None


def read_env_var(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    if os.name == "nt":
        return _read_windows_env_var(name)

    return None

