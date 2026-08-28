import asyncio

OK_BODY = b'{"status":"ok"}'


async def handle_health_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request_line = (await reader.readline()).decode("ascii", errors="replace").strip()
        while await reader.readline() not in {b"\r\n", b"\n", b""}:
            pass

        if request_line in {"GET / HTTP/1.1", "GET /health HTTP/1.1"}:
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 15\r\n"
                b"Connection: close\r\n\r\n"
                + OK_BODY
            )
        else:
            response = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        writer.write(response)
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def start_health_server(port: int) -> asyncio.AbstractServer:
    return await asyncio.start_server(handle_health_request, "0.0.0.0", port)
