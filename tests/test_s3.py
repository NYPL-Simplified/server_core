import os
import contextlib
from PIL import Image
from StringIO import StringIO
from nose.tools import (
    assert_raises,
    assert_raises_regexp,
    eq_,
    set_trace,
)
from . import (
    DatabaseTest
)
from model import (
    DataSource,
    ExternalIntegration,
    Hyperlink,
    Representation,
)
from s3 import (
    S3Uploader,
    MockS3Pool,
)
from util.mirror import MirrorUploader
from config import CannotLoadConfiguration

class S3UploaderTest(DatabaseTest):

    def _integration(self, **settings):
        """Create and configure a simple S3 integration."""
        integration = self._external_integration(
            ExternalIntegration.S3, settings=settings
        )
        integration.goal = ExternalIntegration.STORAGE_GOAL
        integration.username = 'username'
        integration.password = 'password'
        return integration

    def _uploader(self, pool_class=None, **settings):
        """Create a simple S3Uploader."""
        integration = self._integration(**settings)
        return S3Uploader(integration, pool_class=pool_class)


class TestS3Uploader(S3UploaderTest):

    def test_instantiation(self):
        # If there is a configuration but it's misconfigured, an error
        # is raised.
        integration = self._external_integration(
            ExternalIntegration.S3, goal=ExternalIntegration.STORAGE_GOAL
        )
        assert_raises_regexp(
            CannotLoadConfiguration, 'without both access_key and secret_key',
            MirrorUploader.implementation, integration
        )

        # Otherwise, it builds just fine.
        integration.username = 'your-access-key'
        integration.password = 'your-secret-key'
        uploader = MirrorUploader.implementation(integration)
        eq_(True, isinstance(uploader, S3Uploader))


    def test_custom_pool_class(self):
        """You can specify a pool class to use instead of tinys3.Pool."""
        integration = self._integration()
        uploader = S3Uploader(integration, MockS3Pool)
        assert isinstance(uploader.pool, MockS3Pool)

    def test_get_bucket(self):
        buckets = {
            S3Uploader.OA_CONTENT_BUCKET_KEY : 'banana',
            S3Uploader.BOOK_COVERS_BUCKET_KEY : 'bucket'
        }
        buckets_plus_irrelevant_setting = dict(buckets)
        buckets_plus_irrelevant_setting['not-a-bucket-at-all'] = "value"
        uploader = self._uploader(**buckets_plus_irrelevant_setting)

        # This S3Uploader knows about the configured buckets.  It
        # wasn't informed of the irrelevant 'not-a-bucket-at-all'
        # setting.
        eq_(buckets, uploader.buckets)

        # get_bucket just does a lookup in .buckets
        uploader.buckets['foo'] = object()
        result = uploader.get_bucket('foo')
        eq_(uploader.buckets['foo'], result)

    def test_url(self):
        uploader = self._uploader()
        m = uploader.url
        eq_("http://s3.amazonaws.com/a-bucket/a-path", m("a-bucket", "a-path"))
        eq_("http://s3.amazonaws.com/a-bucket/a-path", m("a-bucket", "/a-path"))
        eq_("http://a-bucket.com/a-path", m("http://a-bucket.com/", "a-path"))
        eq_("https://a-bucket.com/a-path", 
            m("https://a-bucket.com/", "/a-path"))

    def test_cover_image_root(self):
        bucket = u'test-book-covers-s3-bucket'
        uploader = self._uploader()

        gutenberg_illustrated = DataSource.lookup(
            self._db, DataSource.GUTENBERG_COVER_GENERATOR)
        overdrive = DataSource.lookup(self._db, DataSource.OVERDRIVE)

        eq_("http://s3.amazonaws.com/test-book-covers-s3-bucket/Gutenberg%20Illustrated/",
            uploader.cover_image_root(bucket, gutenberg_illustrated))
        eq_("http://s3.amazonaws.com/test-book-covers-s3-bucket/Overdrive/",
            uploader.cover_image_root(bucket, overdrive))
        eq_("http://s3.amazonaws.com/test-book-covers-s3-bucket/scaled/300/Overdrive/",
            uploader.cover_image_root(bucket, overdrive, 300))

    def test_content_root(self):
        bucket = u'test-open-access-s3-bucket'
        uploader = self._uploader()
        m = uploader.content_root
        eq_(
            "http://s3.amazonaws.com/test-open-access-s3-bucket/",
            m(bucket)
        )

        # There is nowhere to store content that is not open-access.
        assert_raises(
            NotImplementedError,
            m, bucket, open_access=False
        )

    def test_book_url(self):
        identifier = self._identifier(foreign_id="ABOOK")
        buckets = {S3Uploader.OA_CONTENT_BUCKET_KEY : 'thebooks'}
        uploader = self._uploader(**buckets)
        m = uploader.book_url

        eq_(u'http://s3.amazonaws.com/thebooks/Gutenberg%20ID/ABOOK.epub',
            m(identifier))

        # The default extension is .epub, but a custom extension can
        # be specified.
        eq_(u'http://s3.amazonaws.com/thebooks/Gutenberg%20ID/ABOOK.pdf', 
            m(identifier, extension='pdf'))

        eq_(u'http://s3.amazonaws.com/thebooks/Gutenberg%20ID/ABOOK.pdf', 
            m(identifier, extension='.pdf'))

        # If a data source is provided, the book is stored underneath the
        # data source.
        unglueit = DataSource.lookup(self._db, DataSource.UNGLUE_IT)
        eq_(u'http://s3.amazonaws.com/thebooks/unglue.it/Gutenberg%20ID/ABOOK.epub',
            m(identifier, data_source=unglueit))

        # If a title is provided, the book's filename incorporates the
        # title, for the benefit of people who download the book onto
        # their hard drive.
        eq_(u'http://s3.amazonaws.com/thebooks/Gutenberg%20ID/ABOOK/On%20Books.epub',
            m(identifier, title="On Books"))

        # Non-open-access content can't be stored.
        assert_raises(NotImplementedError, m, identifier, open_access=False)

    def test_cover_image_url(self):
        identifier = self._identifier(foreign_id="ABOOK")
        buckets = {S3Uploader.BOOK_COVERS_BUCKET_KEY : 'thecovers'}
        uploader = self._uploader(**buckets)
        m = uploader.cover_image_url

        unglueit = DataSource.lookup(self._db, DataSource.UNGLUE_IT)
        identifier = self._identifier(foreign_id="ABOOK")
        eq_(u'http://s3.amazonaws.com/thecovers/scaled/601/unglue.it/Gutenberg%20ID/ABOOK/filename',
            m(unglueit, identifier, "filename", scaled_size=601))

    def test_bucket_and_filename(self):
        m = S3Uploader.bucket_and_filename
        eq_(("bucket", "directory/filename.jpg"),
            m("https://s3.amazonaws.com/bucket/directory/filename.jpg"))

        eq_(("book-covers.nypl.org", "directory/filename.jpg"),
            m("http://book-covers.nypl.org/directory/filename.jpg"))


class TestUpload(S3UploaderTest):

    def test_automatic_conversion_while_mirroring(self):
        edition, pool = self._edition(with_license_pool=True)
        original = self._url

        # Create an SVG cover for the book.
        svg = """<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"
  "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">

<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">
    <ellipse cx="50" cy="25" rx="50" ry="25" style="fill:blue;"/>
</svg>"""
        hyperlink, ignore = pool.add_link(
            Hyperlink.IMAGE, original, edition.data_source, 
            Representation.SVG_MEDIA_TYPE,
            content=svg)

        # 'Upload' it to S3.
        s3pool = MockS3Pool('username', 'password')
        s3 = self._uploader(s3pool)
        s3.mirror_one(hyperlink.resource.representation)
        [[filename, data, bucket, media_type, ignore]] = s3pool.uploads

        # The thing that got uploaded was a PNG, not the original SVG
        # file.
        eq_(Representation.PNG_MEDIA_TYPE, media_type)
        assert 'PNG' in data
        assert 'svg' not in data
