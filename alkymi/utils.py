import subprocess


def call(command: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(command, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(proc.stdout)
    print(proc.stderr)
    proc.check_returncode()
    return proc
