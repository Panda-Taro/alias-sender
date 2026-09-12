"""OSのIPアドレス取得 (REQ-H09, ⑤h IPアドレスはOS管理・参照専用)。"""

import socket


def get_os_ip_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                addresses.add(ip)
    except socket.gaierror:
        pass
    return sorted(addresses) or ["127.0.0.1"]


def get_primary_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        addrs = get_os_ip_addresses()
        return addrs[0] if addrs else "127.0.0.1"
