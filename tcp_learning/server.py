
import asyncio

async def handle_client(reader, writer):
    print("Client connected")

    packet = b"HELLO"

    # نحسب طول البيانات
    length = len(packet)

    # نحول الطول إلى بايتين
    header = length.to_bytes(2, byteorder="big")

    # نرسل الحزمة مقسمة لاختبار الاستقبال
    writer.write(header[:1])
    await writer.drain()
    await asyncio.sleep(1)

    writer.write(header[1:] + packet[:2])
    await writer.drain()
    await asyncio.sleep(1)

    writer.write(packet[2:])
    await writer.drain()

    print("Packet sent")

    await asyncio.sleep(2)
    writer.close()
    await writer.wait_closed()


async def main():
    server = await asyncio.start_server(
        handle_client,
        "127.0.0.1",
        9000
    )

    print("Server is listening on port 9000")

    async with server:
        await server.serve_forever()


asyncio.run(main())
