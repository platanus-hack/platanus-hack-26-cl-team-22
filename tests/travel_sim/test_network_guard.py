import socket


def test_guard_blocks_bypasses():
    import pytest
    for call in (lambda: socket.socket().connect_ex(("1.1.1.1", 443)),
                 lambda: socket.socket().connect(("/1.1.1.1", 80)),
                 lambda: socket.create_connection(("example.com", 80), timeout=1)):
        with pytest.raises(AssertionError):
            call()
