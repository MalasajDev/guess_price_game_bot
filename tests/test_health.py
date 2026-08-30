import asyncio

import pytest

from guess_price_bot.health import start_health_server


async def request(server_port: int, path: str, *, method: str = "GET") -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", server_port)
    writer.write(f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response


@pytest.mark.asyncio
async def test_health_route_returns_json_ok() -> None:
    server = await start_health_server(0)
    port = server.sockets[0].getsockname()[1]
    try:
        response = await request(port, "/health")
    finally:
        server.close()
        await server.wait_closed()

    assert response == (
        b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
        b'Content-Length: 15\r\nConnection: close\r\n\r\n{"status":"ok"}'
    )


@pytest.mark.asyncio
async def test_unknown_health_route_returns_not_found() -> None:
    server = await start_health_server(0)
    port = server.sockets[0].getsockname()[1]
    try:
        response = await request(port, "/unknown")
    finally:
        server.close()
        await server.wait_closed()

    assert response.startswith(b"HTTP/1.1 404 Not Found\r\n")


@pytest.mark.asyncio
async def test_health_route_accepts_uptimerobot_head_request() -> None:
    server = await start_health_server(0)
    port = server.sockets[0].getsockname()[1]
    try:
        response = await request(port, "/health", method="HEAD")
    finally:
        server.close()
        await server.wait_closed()

    assert response == (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        b"Content-Length: 15\r\nConnection: close\r\n\r\n"
    )
