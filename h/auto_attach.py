import subprocess, time

for i in range(60):
    result = subprocess.run(
        ["frida-ps", "-D", "emulator-5554"],
        capture_output=True, text=True, timeout=10
    )
    for line in result.stdout.splitlines():
        if "onemt" in line.lower():
            print(f"FOUND: {line.strip()}")
            # Extract PID
            pid = line.strip().split()[0]
            print(f"PID: {pid}")
            # Now attach
            print("Attaching Frida...")
            proc = subprocess.Popen(
                ["frida", "-D", "emulator-5554", "-p", pid, "-l", r"E:\osmanli\capture_token.js"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            # Stream output
            try:
                for out_line in proc.stdout:
                    print(out_line, end="")
            except KeyboardInterrupt:
                proc.kill()
            exit(0)
    print(f"Waiting... attempt {i+1}/60")
    time.sleep(5)

print("Game not found after 5 minutes")
