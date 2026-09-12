from app.services.sdp_utils import detect_media_type, parse_transport_params

SDP_VIDEO = """v=0
o=- 123 456 IN IP4 192.168.1.10
s=SB1 Video
c=IN IP4 239.1.1.1/32
t=0 0
m=video 5000 RTP/AVP 96
a=rtpmap:96 raw/90000
a=source-filter: incl IN IP4 239.1.1.1 192.168.1.10
"""

SDP_AUDIO = """v=0
o=- 123 456 IN IP4 192.168.1.10
s=SB1 Audio
c=IN IP4 239.1.1.2/32
t=0 0
m=audio 5010 RTP/AVP 97
a=rtpmap:97 L24/48000/2
"""

SDP_ANC = """v=0
o=- 123 456 IN IP4 192.168.1.10
s=SB1 ANC
c=IN IP4 239.1.1.3/32
t=0 0
m=video 5020 RTP/AVP 98
a=rtpmap:98 smpte291/90000
"""


def test_detect_video():
    assert detect_media_type(SDP_VIDEO) == "video"


def test_detect_audio():
    assert detect_media_type(SDP_AUDIO) == "audio"


def test_detect_ancillary_from_smpte291():
    assert detect_media_type(SDP_ANC) == "ancillary"


def test_detect_empty():
    assert detect_media_type("") is None


def test_parse_transport_params():
    params = parse_transport_params(SDP_VIDEO)
    assert params["destination_ip"] == "239.1.1.1"
    assert params["destination_port"] == 5000
    assert params["source_ip"] == "192.168.1.10"
    assert params["rtp_enabled"] is True
