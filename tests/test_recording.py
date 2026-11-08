from alpha_led_sign import Frame, Message, Sign, models
from alpha_led_sign.protocol.commands import WriteText
from tests.fakes import FakeTransport
from tests.recording import RecordingTransport
from tests.vectors import TABLE_41


def test_writes_pauses_and_reads_are_recorded_in_order_and_passed_through() -> None:
    fake = FakeTransport(responses=[b"\x01000", b"\x04"])
    recording = RecordingTransport(fake)

    recording.write(b"\x01Z00")
    recording.pause(0.1)
    first = recording.read(1.0)
    recording.read(0)  # nothing waiting: not recorded
    second = recording.read(1.0)

    assert (first, second) == (b"\x01000", b"\x04")
    assert recording.events == [
        ("write", b"\x01Z00"),
        ("pause", 0.1),
        ("read", b"\x01000"),
        ("read", b"\x04"),
    ]
    assert fake.events == [("write", b"\x01Z00"), ("pause", 0.1)]
    assert recording.written == b"\x01Z00"
    assert recording.received == b"\x01000\x04"


def test_a_sign_over_a_recording_transport_records_the_packet_of_table_41() -> None:
    recording = RecordingTransport(FakeTransport())
    sign = Sign(recording, model=models.GENERIC)

    sign.send(WriteText("A", Message(Frame(None, content="HELLO"))))

    assert recording.written == TABLE_41


def test_events_serialize_bytes_as_hex() -> None:
    recording = RecordingTransport(FakeTransport())
    recording.write(b"\x01Z")
    recording.pause(3.0)

    assert recording.to_json() == [
        {"event": "write", "hex": "015a"},
        {"event": "pause", "seconds": 3.0},
    ]


def test_close_closes_the_inner_transport() -> None:
    fake = FakeTransport()
    RecordingTransport(fake).close()

    assert fake.closed
