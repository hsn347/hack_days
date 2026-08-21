import base64

# من الـ capture
resp_b64 = "TWpVNUBhMjlvWDJkaGJXVmZNalk9QE1URTVMamd1TWpFekxqRXhNUT09QE5EQXdNQT09QE1qVXdNRFU1QE1UQTJNVE0zTVRjPUBATUE5PQ=="
dh_ch    = "xMMTfBKD2Og="
dh_cpub  = "UK4i9wWehlA="
dh_spub  = "2r54rGfSwLY="
dh_hmac  = "uBGdq45CpCg="

# 1. فك تشفير الـ 200 response
outer = base64.b64decode(resp_b64).decode('latin1')
print("[200 RESPONSE DECODED]")
print("Raw:", repr(outer))
print()

fields = outer.split('@')
print(f"Total fields: {len(fields)}")
for i, f in enumerate(fields):
    if not f:
        print(f"  Field {i}: (empty)")
        continue
    try:
        pad = '=' * (-len(f) % 4)
        val = base64.b64decode(f + pad).decode('utf-8', errors='replace')
        print(f"  Field {i}: b64({f!r}) = {val!r}")
    except Exception as e:
        print(f"  Field {i}: {f!r} (raw, err={e})")

# 2. حجم أجزاء الـ token
print()
print("[TOKEN PARTS ANALYSIS]")
token_raw = "kJolk/m4yia9lzt0D9nphbWPoFxgnoQZBAxno1Axi3oRisOM0ITX4wnOVba693K/9QO/lwxwxfWQe/yguKO8wWKMFcKUChA1wgS1PnhSbwafp/BLVN3LTzHXJk1p2+UqCM00m81q1Dx2aalDAZup0DRGfVIG/F6DKi99If6IkAk06FUsELXI7bbu7LlEKgXb/kMNnzSLI+VEI7wmqq2Y890stvs7sUwoVMj49I8lALKLD/aEUjbcow==@q+4YcRUzYoKEDQdeGuN+7A==@jXwJN2g7k0Pg2EtEJKQHleEbW5WWntzXDY7RU6+/00Iyskx6duBjS1u87isiZCjMGz3Z4YhDdN444fyZLozrwl7GTet3IW8hRN7DBrjfGp0=@knS+/fNE0P4=@Yr1MH5+KHtE="

parts = token_raw.split('@')
for i, p in enumerate(parts):
    try:
        raw_len = len(base64.b64decode(p + '=' * (-len(p) % 4)))
        print(f"  Part {i+1}: b64_len={len(p)} raw_bytes={raw_len}")
    except:
        print(f"  Part {i+1}: b64_len={len(p)}")
