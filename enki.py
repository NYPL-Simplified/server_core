rom nose.tools import set_trace
from collections import defaultdict
import datetime
import base64
import os
import json
import logging
import re

from config import (
    Configuration,
    temp_config,
)

from util import LanguageCodes
from util.jsonparser import JSONParser
from util.http import (
    HTTP,
    RemoteIntegrationException,
)
from coverage import CoverageFailure
from model import (
    get_one_or_create,
    Collection,
    Contributor,
    DataSource,
    DeliveryMechanism,
    LicensePool,
    Edition,
    Identifier,
    Library,
    Representation,
    Subject,
)

from metadata_layer import (
    SubjectData,
    ContributorData,
    FormatData,
    IdentifierData,
    CirculationData,
    Metadata,
)

from config import Configuration
from coverage import BibliographicCoverageProvider

# TODO Remove unnecessary import statements

class EnkiAPI(object):
    # should confirm this
    PRODUCTION_BASE_URL = "http://enkilibrary.org/API/"

    # may or may not be useful
    DATE_FORMAT = "%m-%d-%Y %H:%M:%S"

    log = logging.getLogger("Enki API")
    # TODO: make sure this logger exists :-)

    def __init__(self, _db, collection):
        if collection.protocol != collection.ENKI:
            raise ValueError(
                "Collection protocol is %s, but passed into EnkiAPI!" %
                collection.protocol
            )

        self._db = _db

        self.library_id = collection.external_account_id.encode("utf8")
        self.username = collection.external_integration.username.encode("utf8")
        self.password = collection.external_integration.password.encode("utf8")

        base_url = collection.external_integration.url or self.PRODUCTION_BASE_URL

        self.base_url = base_url

        if (not self.library_id or not self.username
            or not self.password):
            raise CannotLoadConfiguration(
                "Enki configuration is incomplete."
            )

        self.token = None

class MockEnkiAPI(EnkiAPI):
    #TODO

class EnkiBibliographicCoverageProvider(BibliographicCoverageProvider):
    #TODO

class EnkiParser(object):
    #TODO
