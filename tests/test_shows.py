import pytest

from u2lib.shows import exclusion_reason, is_cancelled


@pytest.mark.parametrize(
    ("info", "reason"),
    [
        ("Cancelled", "cancelled"),
        ("Canceled due to Bono's injury", "cancelled"),
        ("Show was cancelled because of the weather", "cancelled"),
        ("This concert has been called off", "cancelled"),
        ("The show did not take place", "cancelled"),
        ("Cancellation announced on the day", "cancelled"),
        ("Postponed", "postponed"),
        ("Show postponed to 3 June 2011", "postponed"),
        ("Rescheduled to 21-07-2011", "postponed"),
        ("Concert was postponed", "postponed"),
    ],
)
def test_excluded(info, reason):
    assert exclusion_reason(info) == reason
    assert is_cancelled(info)


@pytest.mark.parametrize(
    "info",
    [
        None,
        "",
        "First show of the tour",
        "Postponed from 25-05-2011",
        "Rescheduled from 2010 after Bono's back surgery",
        "Originally scheduled for 13-06-2010",
        "Make-up show",
        "Rain delay of 40 minutes",
    ],
)
def test_show_happened(info):
    assert exclusion_reason(info) is None
    assert not is_cancelled(info)


# T-18: real setlist.fm show info texts reviewed on lk_silver.dbo.show / show_excluded (run 20261021T150024Z).
def test_real_cancelled_show():
    assert exclusion_reason("this show never happened") == "cancelled"


@pytest.mark.parametrize(
    "info",
    [
        # Part of the show was cancelled, the show itself happened.
        'This show is infamous for Bono losing his voice during "God Part II" and never regaining it. '
        "As a result, the encore with B.B. King was cancelled.",
        # Stopped mid-show, songs were played.
        'The gig was stopped after "Beautiful Day" and could not be continued due to Bono losing his voice. '
        "New date: Tuesday, November 13th, 2018",
        '"Gloria" has to be stopped mid-song due to an armed audience member in the front row.',
        "Adam Clayton was severely hung over and could not perform as a result, and the show could not be postponed",
        # Make-up shows with "make up" written as two words.
        "This is one of three shows scheduled to make up for the postponed show that was planned to take place on "
        "4 April 2006 at Yokohama's Nissan Stadium.",
        "U2 recorded their appearance at Tonight Show With Jimmy Fallon after postponing their November 2014 "
        "residency at the show.",
        "There are unconfirmed claims that early versions of October songs were rehearsed. Other equally "
        "unconfirmed reports state the band did not even soundcheck.",
        "Dress rehearsal",
    ],
)
def test_real_show_happened(info):
    assert exclusion_reason(info) is None


def test_misdated_duplicate_is_not_detected_by_text_rule():
    # setlist 3d6f14f (1979-02-03, 0 songs): a duplicate of an earlier date, not a cancellation. The text rule
    # rightly leaves it alone; whether to exclude it as `duplicate` is an open question for Vini (T-18).
    assert exclusion_reason("This show happened a week earlier.") is None
