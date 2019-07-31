# encoding: utf-8
from io import StringIO
import datetime
import os
import sys
import site
import re
import tempfile

from nose.tools import (
    assert_raises,
    assert_raises_regexp,
    assert_not_equal,
    eq_,
    set_trace,
)

from ..model import (
    Contributor,
    DataSource,
    Work,
    Identifier,
    Edition,
    create,
    get_one,
    get_one_or_create,
)

from . import (
    DatabaseTest,
    DummyHTTPClient,
)

from ..util.personal_names import (
    display_name_to_sort_name,
)
from ..mock_analytics_provider import MockAnalyticsProvider



class TestNameConversions(DatabaseTest):

    def test_display_name_to_sort_name(self):
        # Make sure the sort name algorithm processes the messy reality of contributor
        # names in a way we expect.

        # no input means don't do anything
        sort_name = display_name_to_sort_name(None)
        eq_(None, sort_name)

        # already sort-ready input means don't do anything
        sort_name = display_name_to_sort_name("Bitshifter, Bob")
        eq_("Bitshifter, Bob", sort_name)

        sort_name = display_name_to_sort_name("Prince")
        eq_("Prince", sort_name)

        sort_name = display_name_to_sort_name("Pope Francis")
        eq_("Pope, Francis", sort_name)

        sort_name = display_name_to_sort_name("Bob Bitshifter")
        eq_("Bitshifter, Bob", sort_name)

        # foreign characters don't confuse the algorithm
        sort_name = display_name_to_sort_name("Боб Битшифтер")
        eq_("Битшифтер, Боб", sort_name)

        sort_name = display_name_to_sort_name("Bob Bitshifter, Jr.")
        eq_("Bitshifter, Bob Jr.", sort_name)

        sort_name = display_name_to_sort_name("Bob Bitshifter, III")
        eq_("Bitshifter, Bob III", sort_name)

        # already having a comma still gets good results
        sort_name = display_name_to_sort_name("Bob, The Grand Duke of Awesomeness")
        eq_("Bob, Duke of Awesomeness The Grand", sort_name)

        # all forms of PhD are recognized
        sort_name = display_name_to_sort_name("John Doe, PhD")
        eq_("Doe, John PhD", sort_name)
        sort_name = display_name_to_sort_name("John Doe, Ph.D.")
        eq_("Doe, John PhD", sort_name)
        sort_name = display_name_to_sort_name("John Doe, Ph D")
        eq_("Doe, John PhD", sort_name)
        sort_name = display_name_to_sort_name("John Doe, Ph. D.")
        eq_("Doe, John PhD", sort_name)
        sort_name = display_name_to_sort_name("John Doe, PHD")
        eq_("Doe, John PhD", sort_name)

        sort_name = display_name_to_sort_name("John Doe, M.D.")
        eq_("Doe, John MD", sort_name)

        # corporate name is unchanged
        sort_name = display_name_to_sort_name("Church of Jesus Christ of Latter-day Saints")
        eq_("Church of Jesus Christ of Latter-day Saints", sort_name)


    def test_name_tidy(self):
        # remove improper comma
        sort_name = display_name_to_sort_name("Bitshifter, Bob,")
        eq_("Bitshifter, Bob", sort_name)

        # remove improper period
        sort_name = display_name_to_sort_name("Bitshifter, Bober.")
        eq_("Bitshifter, Bober", sort_name)

        # retain proper period
        sort_name = display_name_to_sort_name("Bitshifter, B.")
        eq_("Bitshifter, B.", sort_name)





