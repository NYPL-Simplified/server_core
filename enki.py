from nose.tools import set_trace
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
    availability_endpoint = "ListAPI"

    # may or may not be useful
    DATE_FORMAT = "%m-%d-%Y %H:%M:%S"

    log = logging.getLogger("Enki API")
    # TODO: make sure this logger exists :-)
    def __init__(self, _db, username=None, library_id=None, password=None,
                 base_url=None):
        self._db = _db
        (env_library_id, env_username,
         env_password, env_base_url) = self.environment_values()
        self.library_id = library_id or env_library_id
        self.username = username or env_username
        self.password = password or env_password
        self.base_url = base_url or env_base_url
        if self.base_url == 'qa':
            self.base_url = self.QA_BASE_URL
        elif self.base_url == 'production':
            self.base_url = self.PRODUCTION_BASE_URL
        self.token = "mock_token"

    @classmethod
    def environment_values(cls):
	print "---------------\nIN DEF ENVIRONMENT_VALUES"
        config = Configuration.integration('Enki')
	print "Config is %s" % config
        values = []
        for name in [
                'library_id',
		'username',
		'password',
		'url'
        ]:
            value = config.get(name)
            if value:
                value = value.encode("utf8")
            values.append(value)
        return values

    @classmethod
    def from_environment(cls, _db):
	values = cls.environment_values()
	if len([x for x in values if not x]):
	    cls.log.info( "No Enki client configured" )
	    return None
        return cls(_db)	

    @property
    def source(self):
        return DataSource.lookup(self._db, DataSource.ENKI)

    @property
    def authorization_headers(self):
        authorization = u":".join([self.username, self.password, self.library_id])
        authorization = authorization.encode("utf_16_le")
        authorization = base64.standard_b64encode(authorization)
        return dict(Authorization="Basic " + authorization)

    def refresh_bearer_token(self):
        url = self.base_url + self.access_token_endpoint
        headers = self.authorization_headers
        response = self._make_request(
            url, 'post', headers, allowed_response_codes=[200]
        )
        return self.parse_token(response.content)

    def request(self, url, method='get', extra_headers={}, data=None,
                params=None, exception_on_401=False):
        """Make an HTTP request, acquiring/refreshing a bearer token
        if necessary.
        """
        if not self.token:
            self.token = self.refresh_bearer_token()

        headers = dict(extra_headers)
        headers['Authorization'] = "Bearer " + self.token
        headers['Library'] = self.library_id
        if exception_on_401:
            disallowed_response_codes = ["401"]
        else:
            disallowed_response_codes = None
        response = self._make_request(
            url=url, method=method, headers=headers,
            data=data, params=params,
            disallowed_response_codes=disallowed_response_codes
        )
        if response.status_code == 401:
            # This must be our first 401, since our second 401 will
            # make _make_request raise a RemoteIntegrationException.
            #
            # The token has expired. Get a new token and try again.
            self.token = None
            return self.request(
                url=url, method=method, extra_headers=extra_headers,
                data=data, params=params, exception_on_401=True
            )
        else:
            return response

    def availability(self, patron_id=None, since=None, title_ids=[]):
        url = self.base_url + self.availability_endpoint
        args = dict()
	#TODO Args for API calls go here
        """if since:
            since = since.strftime(self.DATE_FORMAT)
            args['updatedDate'] = since
        if patron_id:
            args['patronId'] = patron_id
        if title_ids:
            args['titleIds'] = ','.join(title_ids)"""
	args['method'] = "getUpdateTitles"
	args['id'] = "secontent"
	print "Making a request to %s" % url
	response = self.request(url, params=args)
	if response:
            print "We got a response!"
        else:
            print "There was no response!"
        return response

    @classmethod
    def create_identifier_strings(cls, identifiers):
        identifier_strings = []
        for i in identifiers:
            if isinstance(i, Identifier):
                value = i.identifier
            else:
                value = i
            identifier_strings.append(value)

        return identifier_strings

    @classmethod
    def parse_token(cls, token):
        data = json.loads(token)
        return data['access_token']

    def _make_request(self, url, method, headers, data=None, params=None,
                      **kwargs):
        """Actually make an HTTP request."""
        return HTTP.request_with_timeout(
            method, url, headers=headers, data=data,
            params=params, **kwargs
        )

class MockEnkiAPI(EnkiAPI):
    #TODO
    pass

class EnkiBibliographicCoverageProvider(BibliographicCoverageProvider):
    #TODO
    """Fill in bibliographic metadata for Enki records.

    Currently this is only used by BibliographicRefreshScript. It's
    not normally necessary because the Enki API combines
    bibliographic and availability data.
    """
    def __init__(self, _db, metadata_replacement_policy=None, enki_api=None,
                 input_identifier_types=None, input_identifiers=None, **kwargs):
        """
        :param input_identifier_types: Passed in by RunCoverageProviderScript, data sources to get coverage for.
        :param input_identifiers: Passed in by RunCoverageProviderScript, specific identifiers to get coverage for.
        """
        self.parser = BibliographicParser()
        super(EnkiBibliographicCoverageProvider, self).__init__(
            _db, enki_api, DataSource.ENKI,
            batch_size=25,
            metadata_replacement_policy=metadata_replacement_policy,
            **kwargs
        )

    def process_batch(self, identifiers):
        identifier_strings = self.api.create_identifier_strings(identifiers)
        response = self.api.availability(title_ids=identifier_strings)
        seen_identifiers = set()
        batch_results = []
        for metadata, availability in self.parser.process_all(response.content):
            identifier, is_new = metadata.primary_identifier.load(self._db)
            if not identifier in identifiers:
                # Enki told us about a book we didn't ask
                # for. This shouldn't happen, but if it does we should
                # do nothing further.
                continue
            seen_identifiers.add(identifier.identifier)
            result = self.set_metadata(identifier, metadata)
            if not isinstance(result, CoverageFailure):
                result = self.handle_success(identifier)
            batch_results.append(result)

        # Create a CoverageFailure object for each original identifier
        # not mentioned in the results.
        for identifier_string in identifier_strings:
            if identifier_string not in seen_identifiers:
                identifier, ignore = Identifier.for_foreign_id(
                    self._db, Identifier.ENKI_ID, identifier_string
                )
                result = CoverageFailure(
                    identifier, "Book not in collection", data_source=self.output_source, transient=False
                )
                batch_results.append(result)
        return batch_results

    def handle_success(self, identifier):
        return self.set_presentation_ready(identifier)

    def process_item(self, identifier):
        results = self.process_batch([identifier])
        return results[0]

class EnkiParser(JSONParser):
    #TODO
    pass

class BibliographicParser(EnkiParser):
    pass
    #TODO Copied straight from Axis360. Needs work to get enki_monitor to run.
    DELIVERY_DATA_FOR_AXIS_FORMAT = {
        "Blio" : None,
        "Acoustik" : None,
        "ePub" : (Representation.EPUB_MEDIA_TYPE, DeliveryMechanism.ADOBE_DRM),
        "PDF" : (Representation.PDF_MEDIA_TYPE, DeliveryMechanism.ADOBE_DRM),
    }

    log = logging.getLogger("Axis 360 Bibliographic Parser")

    @classmethod
    def parse_list(self, l):
        """Turn strings like this into lists:

        FICTION / Thrillers; FICTION / Suspense; FICTION / General
        Ursu, Anne ; Fortune, Eric (ILT)
        """
        return [x.strip() for x in l.split(";")]

    def __init__(self, include_availability=True, include_bibliographic=True):
        self.include_availability = include_availability
        self.include_bibliographic = include_bibliographic

    def process_all(self, string):
        for i in super(BibliographicParser, self).process_all(
                string, "//axis:title"):#, self.NS):
            yield i

    def extract_availability(self, circulation_data, element, ns):
	primary_identifier = IdentifierData(Identifier.ENKI_ID, element["id"])
        if not circulation_data:
            circulation_data = CirculationData(
                data_source=DataSource.ENKI,
                primary_identifier=primary_identifier,
            )

        circulation_data.licenses_owned=1
        circulation_data.licenses_available=1
        circulation_data.licenses_reserved=0
        circulation_data.patrons_in_hold_queue=0

        return circulation_data


    # Axis authors with a special role have an abbreviation after their names,
    # e.g. "San Ruby (FRW)"
    role_abbreviation = re.compile("\(([A-Z][A-Z][A-Z])\)$")
    generic_author = object()
    role_abbreviation_to_role = dict(
        INT=Contributor.INTRODUCTION_ROLE,
        EDT=Contributor.EDITOR_ROLE,
        PHT=Contributor.PHOTOGRAPHER_ROLE,
        ILT=Contributor.ILLUSTRATOR_ROLE,
        TRN=Contributor.TRANSLATOR_ROLE,
        FRW=Contributor.FOREWORD_ROLE,
        ADP=generic_author, # Author of adaptation
        COR=generic_author, # Corporate author
    )

    @classmethod
    def parse_contributor(cls, author, primary_author_found=False):
        if primary_author_found:
            default_author_role = Contributor.AUTHOR_ROLE
        else:
            default_author_role = Contributor.PRIMARY_AUTHOR_ROLE
        role = default_author_role
        match = cls.role_abbreviation.search(author)
        if match:
            role_type = match.groups()[0]
            role = cls.role_abbreviation_to_role.get(
                role_type, Contributor.UNKNOWN_ROLE)
            if role is cls.generic_author:
                role = default_author_role
            author = author[:-5].strip()
        return ContributorData(
            sort_name=author, roles=role)

    def extract_bibliographic(self, element, ns):
        primary_identifier = IdentifierData(Identifier.ENKI_ID, element["id"])
	metadata = Metadata(
            data_source=DataSource.ENKI,
            title=element["title"],
            #language="ENGLISH",
            medium=Edition.BOOK_MEDIUM,
            #series=series,
            publisher=element["publisher"],
            #imprint=imprint,
            #published=publication_date,
            primary_identifier=primary_identifier,
            #identifiers=identifiers,
            #subjects=subjects,
            #contributors=contributors,
        )

        circulationdata = CirculationData(
            data_source=DataSource.ENKI,
            primary_identifier=primary_identifier,
            #formats=formats,
        )

        metadata.circulation = circulationdata
        return metadata


    def process_one(self, element, ns):
        if self.include_bibliographic:
            bibliographic = self.extract_bibliographic(element, ns)
        else:
            bibliographic = None

        passed_availability = None
        if bibliographic and bibliographic.circulation:
            passed_availability = bibliographic.circulation

        if self.include_availability:
            availability = self.extract_availability(circulation_data=passed_availability, element=element, ns=ns)
        else:
            availability = None

        return bibliographic, availability
