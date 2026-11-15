"""Matching Responses to Reads, as pure data: no Transport, no clock.

The rules are docs/spec.md, "Read behavior". The Responses are the manual's worked
examples (tests/vectors.py).
"""

from collections.abc import Sequence

from alpha_led_sign.protocol.commands import ReadDayOfWeek, ReadString, ReadText, Weekday
from alpha_led_sign.protocol.matching import Answer, ResponseMatcher, Skipped
from alpha_led_sign.protocol.message import Frame, Message
from alpha_led_sign.protocol.responses import ResponseError, UnexpectedResponseError
from tests.vectors import NULS, TABLE_46, TABLE_54, TABLE_59

FILE_C = Message(Frame(None, content="FILE C"))
BAD_CHECKSUM = NULS + b"\x01000\x02ACFILE C\x03020D\x04"  # Table 46, checksum off by one


def kinds(outcomes: Sequence[object]) -> list[type]:
    return [type(outcome) for outcome in outcomes]


def test_an_answer_split_across_reads_comes_back_when_it_is_complete() -> None:
    matcher, read = ResponseMatcher(), ReadText("C")
    matcher.sent([read])

    assert matcher.feed(read, TABLE_46[:30]) == []
    assert matcher.feed(read, TABLE_46[30:]) == [Answer(FILE_C)]


def test_a_late_answer_to_an_earlier_read_is_skipped() -> None:
    matcher, read = ResponseMatcher(), ReadText("C")
    matcher.sent([ReadString("2")])  # never answered in time
    matcher.sent([read])

    assert matcher.feed(read, TABLE_59 + TABLE_46) == [Skipped(), Answer(FILE_C)]


def test_only_as_many_responses_are_skipped_as_reads_went_unanswered() -> None:
    matcher, read = ResponseMatcher(), ReadText("C")
    matcher.sent([ReadString("2")])
    matcher.sent([read])

    outcomes = matcher.feed(read, TABLE_59 + TABLE_59)

    assert kinds(outcomes) == [Skipped, UnexpectedResponseError]


def test_a_response_to_another_read_is_an_error_when_no_other_read_is_waiting() -> None:
    matcher, read = ResponseMatcher(), ReadText("C")
    matcher.sent([read])

    assert kinds(matcher.feed(read, TABLE_59)) == [UnexpectedResponseError]


def test_a_garbled_response_is_an_error_and_never_skipped() -> None:
    matcher, read = ResponseMatcher(), ReadText("C")
    matcher.sent([ReadString("2")])
    matcher.sent([read])

    (outcome,) = matcher.feed(read, BAD_CHECKSUM)

    assert isinstance(outcome, ResponseError)
    assert not isinstance(outcome, UnexpectedResponseError)
    assert "checksum" in str(outcome)


def test_responses_discarded_before_a_read_count_as_answered() -> None:
    matcher, read = ResponseMatcher(), ReadText("C")
    matcher.sent([ReadString("2")])
    matcher.discard(TABLE_59)
    matcher.sent([read])

    assert kinds(matcher.feed(read, TABLE_59)) == [UnexpectedResponseError]


def test_the_rest_of_a_response_that_began_before_a_read_is_skipped() -> None:
    matcher = ResponseMatcher()
    day = ReadDayOfWeek()
    matcher.sent([day])
    assert matcher.feed(day, TABLE_54 + TABLE_59[:26]) == [Answer(Weekday.FRIDAY)]

    read = ReadText("C")
    matcher.sent([read])

    assert matcher.feed(read, TABLE_59[26:] + TABLE_46) == [Skipped(), Answer(FILE_C)]


def test_sync_nuls_alone_are_not_a_response_in_progress() -> None:
    matcher, read = ResponseMatcher(), ReadText("C")
    matcher.discard(NULS)
    matcher.sent([read])

    assert matcher.feed(read, TABLE_46) == [Answer(FILE_C)]


def test_a_read_knows_its_answer_without_parsing_it() -> None:
    # Table 46 answers Read TEXT "C" with a Write TEXT ("A") of File "C".
    assert ReadText("C").response_code == "A"
    assert ReadText("C").response_prefix == "C"
    assert ReadString("2").response_code == "G"
