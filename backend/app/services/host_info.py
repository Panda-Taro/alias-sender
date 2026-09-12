"""OSのIPアドレス取得 (REQ-H09, ⑤h IPアドレスはOS管理・参照専用)。

`socket.gethostname()`経由のIP解決は、コンテナのhostnameがOSに設定された
実際のインターフェースIPと一致しない場合がある(特に`--network host`環境)。
そのため、`ip addr`(なければ`ifconfig`)の出力を実際に解析して、OSが認識して
いるIPアドレスをそのまま表示する。
"""

import logging
import re
import socket
import subprocess

logger = logging.getLogger(__name__)

_IP_ADDR_RE = re.compile(r"inet\s+(\d+\.\d+\.\d+\.\d+)/\d+.*?scope\s+(\S+)")
_IFCONFIG_RE = re.compile(r"inet\s+(?:addr:)?(\d+\.\d+\.\d+\.\d+)")


def _run(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            return result.stdout
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _from_ip_addr() -> list[str]:
    output = _run(["ip", "-o", "-4", "addr", "show"])
    if not output:
        return []
    addresses = []
    for line in output.splitlines():
        m = _IP_ADDR_RE.search(line)
        if not m:
            continue
        ip, scope = m.group(1), m.group(2)
        if scope == "host" or ip.startswith("127."):
            continue
        addresses.append(ip)
    return addresses


def _from_ifconfig() -> list[str]:
    output = _run(["ifconfig"])
    if not output:
        return []
    addresses = []
    for line in output.splitlines():
        m = _IFCONFIG_RE.search(line)
        if m and not m.group(1).startswith("127."):
            addresses.append(m.group(1))
    return addresses


def _from_socket() -> list[str]:
    addresses: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                addresses.add(ip)
    except socket.gaierror:
        pass
    return sorted(addresses)


def get_os_ip_addresses() -> list[str]:
    """`ip addr`(Linux)、フォールバックで`ifconfig`、さらにフォールバックで
    ソケットAPIの順にOSのIPアドレスを取得する。"""
    for source in (_from_ip_addr, _from_ifconfig, _from_socket):
        addresses = source()
        if addresses:
            # 順序を保ちつつ重複を除去
            return list(dict.fromkeys(addresses))
    return ["127.0.0.1"]


def get_primary_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        addrs = get_os_ip_addresses()
        return addrs[0] if addrs else "127.0.0.1"
