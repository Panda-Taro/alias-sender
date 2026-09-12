"""SDP解析ユーティリティ。

本システムはReal SenderのSDP本体を一切改変しない(④⑤の大前提)。ここでは
media_type(video/audio/ancillary)の自動判定に必要な最小限の情報のみを
正規表現で読み取る薄いパーサを提供する。ST2110の慣習では、
- ST2110-20(非圧縮映像): m=video ... / rtpmap encoding "raw"
- ST2110-30(音声): m=audio ... / rtpmap encoding "L16"/"L24"/"L32" 等
- ST2110-40(アンシラリ): m=video ... だが rtpmap encoding が "smpte291"
という差異があるため、rtpmapのエンコーディング名を優先的に見る。
"""

import re

_RTPMAP_RE = re.compile(r"^a=rtpmap:\d+\s+([\w-]+)/", re.IGNORECASE)
_MEDIA_RE = re.compile(r"^m=(\w+)\s")


def detect_media_type(sdp_raw: str) -> str | None:
    if not sdp_raw:
        return None

    media_kind: str | None = None
    rtpmap_encoding: str | None = None

    for line in sdp_raw.splitlines():
        line = line.strip()
        m = _MEDIA_RE.match(line)
        if m and media_kind is None:
            media_kind = m.group(1).lower()
            continue
        r = _RTPMAP_RE.match(line)
        if r and rtpmap_encoding is None:
            rtpmap_encoding = r.group(1).lower()

    if rtpmap_encoding == "smpte291":
        return "ancillary"
    if media_kind == "audio":
        return "audio"
    if media_kind == "video":
        return "video"
    return None


_MLINE_RE = re.compile(r"^m=\w+\s+(\d+)\s+\S+\s+(\d+)")
_CLINE_RE = re.compile(r"^c=IN IP4\s+([0-9.]+)(?:/(\d+))?")
_SRCFILTER_RE = re.compile(
    r"^a=source-filter:\s*incl\s+IN\s+IP4\s+([0-9.]+)\s+([0-9.]+)", re.IGNORECASE
)


def parse_transport_params(sdp_raw: str) -> dict:
    """SDPからIS-05 transport_params相当の最小限の情報(送信先IP/ポート、送信元IP)を抽出する。
    SDP本体は改変せず、参照のみ行う。"""
    destination_ip = None
    destination_port = None
    source_ip = None
    rtp_enabled = bool(sdp_raw)

    for line in (sdp_raw or "").splitlines():
        line = line.strip()
        m = _MLINE_RE.match(line)
        if m and destination_port is None:
            destination_port = int(m.group(1))
        c = _CLINE_RE.match(line)
        if c and destination_ip is None:
            destination_ip = c.group(1)
        s = _SRCFILTER_RE.match(line)
        if s:
            source_ip = s.group(2)

    return {
        "source_ip": source_ip,
        "destination_ip": destination_ip,
        "destination_port": destination_port,
        "rtp_enabled": rtp_enabled,
    }


_RTPMAP_FULL_RE = re.compile(r"^a=rtpmap:\d+\s+([\w-]+)/(\d+)(?:/(\d+))?", re.IGNORECASE)
_FMTP_RE = re.compile(r"^a=fmtp:\d+\s+(.*)$")


def parse_flow_technical_params(sdp_raw: str) -> dict:
    """NMOS Flowリソース(video/audio)の技術パラメータ推定に使う、SDPからの
    最小限の抽出。fmtp行のkey=value(;区切り)と、rtpmapのエンコーディング名/
    クロックレート/チャンネル数を読み取る。値が見つからない項目は呼び出し側で
    ブロードキャストの一般的な既定値にフォールバックする(DECISIONS.md参照)。
    """
    params: dict[str, str] = {}
    for line in (sdp_raw or "").splitlines():
        line = line.strip()
        r = _RTPMAP_FULL_RE.match(line)
        if r:
            params.setdefault("encoding", r.group(1).lower())
            params.setdefault("clock_rate", r.group(2))
            if r.group(3):
                params.setdefault("channels", r.group(3))
        f = _FMTP_RE.match(line)
        if f:
            for kv in f.group(1).split(";"):
                kv = kv.strip()
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    params.setdefault(k.strip().lower(), v.strip())
    return params
