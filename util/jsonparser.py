import json

class JSONParser(object):
    """Helper function to parse JSON"""
    def process_all(self, json_data, xpath, namespaces=None, handler=None, parser=None):
        data = json.loads(json_data)
	returned_titles = data["result"]["titles"]
	titles = returned_titles
	for book in returned_titles:
	    print "A book titled '%s'" % book["title"]
	    print book
	    print "\n"
	    data = self.process_one(book, namespaces)
            if data:
                yield data

    def process_one(self, tag, namespaces):
        return None
