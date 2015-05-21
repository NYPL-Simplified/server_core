from lxml import etree
from StringIO import StringIO

class XMLParser(object):

    """Helper functions to process XML data."""

    @classmethod
    def _xpath(cls, tag, expression):
        """Wrapper to do a namespaced XPath expression."""
        return tag.xpath(expression, namespaces=cls.NAMESPACES)

    @classmethod
    def _xpath1(cls, tag, expression):
        """Wrapper to do a namespaced XPath expression."""
        values = cls._xpath(tag, expression)
        if not values:
            return None
        return values[0]

    def _cls(self, tag_name, class_name):
        """Return an XPath expression that will find a tag with the given CSS class."""
        return 'descendant-or-self::node()/%s[contains(concat(" ", normalize-space(@class), " "), " %s ")]' % (tag_name, class_name)

    def text_of_optional_subtag(self, tag, name, namespaces={}):
        tag = self._xpath1(tag, name, namespaces=namespaces)
        if tag is None or tag.text is None:
            return None
        else:
            return unicode(tag.text)
      
    def text_of_subtag(self, tag, name, namespaces={}):
        return unicode(tag.xpath(name, namespaces=namespaces)[0].text)

    def int_of_subtag(self, tag, name, namespaces={}):
        return int(self.text_of_subtag(tag, name, namespaces=namespaces))

    def process_all(self, xml, xpath, namespaces={}, handler=None, parser=None):
        if not parser:
            parser = etree.XMLParser()
        if not handler:
            handler = self.process_one
        if isinstance(xml, basestring):
            root = etree.parse(StringIO(xml), parser)
        else:
            root = xml
        for i in root.xpath(xpath, namespaces=namespaces):
            data = handler(i, namespaces)
            if data:
                yield data

    def process_one(self, tag, namespaces):
        return None
