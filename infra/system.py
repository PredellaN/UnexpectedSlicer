from subprocess import Popen
import sys

class ProcessReader:
    @staticmethod
    def read(proc: Popen[str], wait: float = 0.2) -> tuple[str, str, float | None]:
        if proc.poll() is None:
            return "", "", wait

        if sys.platform.startswith("linux"):
            import select
            
            lines = ""
            while True:
                reads, _, _ = select.select([proc.stdout], [], [], 0)
                if proc.stdout in reads:
                    if not proc.stdout: return "", "", wait
                    line = proc.stdout.readline()
                    if line == "":
                        break ## EOF
                    lines += line
                else:
                    return lines, "", wait

        stdout, stderr = proc.communicate()

        return stdout, stderr, None