import asyncio

async def main():
    reader, writer = await asyncio.open_connection(
        "127.0.0.1",
        9000
    )

    buffer = bytearray()

    while True:

        data = await reader.read(1024)

        if not data:
            print("Connection closed")
            break

        # نضيف البيانات الجديدة إلى Buffer
        buffer.extend(data)

        print("Received:", data)
        print("Buffer:", buffer)

        # هل لدينا Header كامل؟
        if len(buffer) < 2:
            continue

        # نقرأ طول الحزمة من أول بايتين
        packet_length = int.from_bytes(
            buffer[:2],
            byteorder="big"
        )

        # هل وصلت الحزمة كاملة؟
        if len(buffer) < 2 + packet_length:
            continue

        # نستخرج الحزمة
        packet = bytes(buffer[2:2 + packet_length])

        # نحذف الحزمة المستخرجة من Buffer
        del buffer[:2 + packet_length]

        print("Complete packet:", packet)
        print("Decoded:", packet.decode())

    writer.close()
    await writer.wait_closed()


asyncio.run(main())