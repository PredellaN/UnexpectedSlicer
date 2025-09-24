from subprocess import Popen
import sys

class ProcessReader:
    @staticmethod
    def read(proc: Popen[str], wait: float = 0.2) -> tuple[str, str, float | None]:
        if proc.poll() is None:
            # Process running: non-blocking read on Linux
            if sys.platform.startswith("linux"):
                import select
                lines = ""
                while True:
                    reads, _, _ = select.select([proc.stdout], [], [], 0)
                    if proc.stdout in reads and proc.stdout:
                        line = proc.stdout.readline()
                        if line == "":  # EOF
                            break
                        lines += line
                    else:
                        return lines, "", wait
            # Fallback: no stdout until completion
            return "", "", wait

        # Process finished
        stdout, stderr = proc.communicate()
        return stdout, stderr, None