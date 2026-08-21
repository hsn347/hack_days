"""
TCP MITM Proxy - يعترض الاتصال بين المحاكي و login server
يلوغ كل الـ bytes المرسلة والمستلمة كـ base64 وhex ونص

الاستخدام:
1. شغّل هذا السكربت
2. سيشغّل proxy على 127.0.0.1:10002
3. شغّل: adb -s emulator-5554 reverse tcp:10000 tcp:10002
4. بدّل الحساب في اللعبة
5. اقرأ الـ logs
"""
import socket, threading, time, base64

REAL_SERVER = ("119.8.212.255", 10000)
PROXY_PORT  = 10002
LOG_FILE    = "E:/osmanli/mitm_log.txt"

log_fh = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fh.write(msg + "\n")
    log_fh.flush()

def dump(prefix, data):
    if not data: return
    try:
        txt = ""
        for b in data:
            if 32 <= b < 127: txt += chr(b)
            elif b == 10: txt += "\\n"
            else: txt += "."
        b64 = base64.b64encode(data).decode()
        hex_ = data.hex()
        log(f"\n=== {prefix} len={len(data)} ===")
        log(f"TEXT: {txt[:400]}")
        log(f"B64:  {b64[:300]}")
        log(f"HEX:  {hex_[:200]}")
    except: pass

def handle_client(client_sock, addr):
    log(f"\n[PROXY] New connection from {addr}")
    try:
        server_sock = socket.socket()
        server_sock.connect(REAL_SERVER)
        log(f"[PROXY] Connected to {REAL_SERVER}")

        conn_count = [0, 0]  # [client→server, server→client]

        def forward(src, dst, direction):
            while True:
                try:
                    data = src.recv(4096)
                    if not data: break
                    conn_count[0 if direction == "C->S" else 1] += 1
                    dump(direction, data)
                    dst.sendall(data)
                except: break
            try: dst.shutdown(socket.SHUT_WR)
            except: pass

        t1 = threading.Thread(target=forward, args=(client_sock, server_sock, "CLIENT->SERVER"), daemon=True)
        t2 = threading.Thread(target=forward, args=(server_sock, client_sock, "SERVER->CLIENT"), daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()
    except Exception as e:
        log(f"[PROXY ERROR] {e}")
    finally:
        try: client_sock.close()
        except: pass
        try: server_sock.close()
        except: pass
    log("[PROXY] Connection closed")

def main():
    proxy = socket.socket()
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy.bind(("0.0.0.0", PROXY_PORT))
    proxy.listen(5)
    log(f"[PROXY] Listening on 127.0.0.1:{PROXY_PORT}")
    log(f"[PROXY] Forwarding to {REAL_SERVER}")
    log(f"[PROXY] Log file: {LOG_FILE}")
    log("[PROXY] Run: adb -s emulator-5554 reverse tcp:10000 tcp:10002")
    log("[PROXY] Then switch account in game\n")

    while True:
        try:
            client, addr = proxy.accept()
            threading.Thread(target=handle_client, args=(client, addr), daemon=True).start()
        except KeyboardInterrupt:
            break
    proxy.close()
    log_fh.close()

if __name__ == "__main__":
    main()
