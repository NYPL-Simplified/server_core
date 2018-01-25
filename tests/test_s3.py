import os
import contextlib
from PIL import Image
from StringIO import StringIO
from nose.tools import (
    set_trace,
    assert_raises_regexp,
    eq_,
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
    DummyS3Uploader,
    MockS3Pool,
)
from util.mirror import MirrorUploader
from config import CannotLoadConfiguration

class S3UploaderTest(DatabaseTest):

    @property
    def _integration(self):
        """Create and configure a simple S3 integration."""
        integration = self._external_integration(ExternalIntegration.S3)
        integration.goal = ExternalIntegration.STORAGE_GOAL
        integration.username = 'username'
        integration.password = 'password'
        return integration

    def _uploader(self, pool_class=None):
        """Create a simple S3Uploader."""
        integration = self._integration
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

    def test_get_bucket(self):
        buckets = {
            S3Uploader.OA_CONTENT_BUCKET_KEY : 'banana',
            S3Uploader.BOOK_COVERS_BUCKET_KEY : 'bucket'
        }
        integration = self._external_integration(
            ExternalIntegration.S3, goal=ExternalIntegration.STORAGE_GOAL,
            username='access', password='secret', settings=buckets
        )

        uploader = MirrorUploader.implementation(integration)

        # This S3Uploader knows about the configured buckets.
        eq_(buckets, uploader.buckets)

        result = uploader.get_bucket(S3Uploader.OA_CONTENT_BUCKET_KEY)
        eq_('banana', result)

    def test_content_root(self):
        bucket = u'test-open-access-s3-bucket'
        eq_("http://s3.amazonaws.com/test-open-access-s3-bucket/",
            self._uploader().content_root(bucket))

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
        s3pool = MockS3Pool()
        s3 = self._uploader(s3pool)
        s3.mirror_one(hyperlink.resource.representation)
        [[filename, data, bucket, media_type, ignore]] = s3pool.uploads

        # The thing that got uploaded was a PNG, not the original SVG
        # file.
        eq_(Representation.PNG_MEDIA_TYPE, media_type)
        assert 'PNG' in data
        assert 'svg' not in data
