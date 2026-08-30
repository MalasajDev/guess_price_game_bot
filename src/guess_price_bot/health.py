import asyncio

OK_BODY = b'{"status":"ok"}'


async def handle_health_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request_line = (await reader.readline()).decode("ascii", errors="replace").strip()
        while await reader.readline() not in {b"\r\n", b"\n", b""}:
            pass

        parts = request_line.split()
        method, path = parts[:2] if len(parts) >= 2 else ("", "")
        if method in {"GET", "HEAD"} and path in {"/", "/health"}:
            body = b"" if method == "HEAD" else OK_BODY
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 15\r\n"
                b"Connection: close\r\n\r\n"
                + body
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
