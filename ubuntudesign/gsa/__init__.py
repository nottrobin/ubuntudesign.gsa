# Core modules
try:
    from urllib.parse import urlencode
except:
    from urllib import urlencode

# Third party modules
import requests
from lxml import etree


def xml_text(root_element, child_tag):
    if root_element.xpath(child_tag):
        return root_element.xpath(child_tag)[0].text


class GSAClient:
    """
    Query the Google Search Appliance and return results
    as a python dictionary.

    Usage:

    search_client = GSAClient(base_url="http://gsa.example.com/search")
    results = search_client.search("hello world")
    total = search_client.total_results("hello world")
    """

    def __init__(self, base_url):
        self.base_url = base_url

    def total_results(self, query, domains=[]):
        """
        Inexplicably, the GSA returns a completely incorrect total
        This is a hack to get the correct total.

        If you request with start>1000, the GSA returns nothing.
        But if you request with start = 990, it returns the last page
        even if there are only 10 results.

        Therefore this is the way to get the real total
        """

        results = self.search(query, start=990, num=10, domains=domains)

        total = 0

        if results['items']:
            total = results['items'][-1]['index']

        return int(total)

    def search(self, query, start=0, num=10, domains=[]):
        """
        Query the GSA to get response in XML format
        which it will then parse into a dictionary.
        """

        # Filter by domains, if specified
        if domains:
            query += ' (' + " | ".join(domains) + ')'

        # Build the GSA URL
        query_parameters = urlencode({
            'q': query,
            'num': str(num),
            'start': str(start)
        })
        search_url = self.base_url + '?' + query_parameters

        response = requests.get(search_url)

        xml_tree = etree.fromstring(response.content)

        # We're now going to parse the XML items into a hopefully
        # more meaningful dictionary object.
        # To understand the layout of the XML document, see here:
        # https://www.google.com/support/enterprise/static/gsa/docs/admin/70/gsa_doc_set/xml_reference/results_format.html

        results = {
            'estimated_total_results': xml_text(xml_tree, '/GSP/RES/M'),
            'document_filtering': bool(xml_text(xml_tree, '/GSP/RES/FI')),
            'next_url': xml_text(xml_tree, '/GSP/RES/NB/NU'),
            'previous_url': xml_text(xml_tree, '/GSP/RES/NB/PU'),
            'items': []
        }

        item_elements = xml_tree.xpath('/GSP/RES/R')

        for item_element in item_elements:
            item = {
                'index': int(item_element.attrib.get('N')),
                'url': xml_text(item_element, 'U'),
                'encoded_url': xml_text(item_element, 'UE'),
                'title': xml_text(item_element, 'T'),
                'relevancy': xml_text(item_element, 'RK'),
                'appliance_id': xml_text(item_element, 'ENT_SOURCE'),
                'summary': xml_text(item_element, 'S'),
                'language': xml_text(item_element, 'LANG'),
                'details': [],
                'features': {}
            }

            detail_elements = item_element.xpath('FS')

            for detail in detail_elements:
                item['details'].append({
                    detail.attrib['NAME']: detail.attrib['VALUE']
                })

            features_elements = item_element.xpath('HAS/*')

            for feature in features_elements:
                if feature.tag == 'L':
                    item['features']['link_supported'] = True
                if feature.tag == 'C':
                    item['features']['cache'] = {
                        'size': feature.attrib.get('SZ'),
                        'cache_id': feature.attrib.get('CID'),
                        'encoding': feature.attrib.get('ENC')
                    }

            results['items'].append(item)

        return results
