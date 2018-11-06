import scrapelib
import lxml.etree
import feedparser

class HouseCommittee(scrapelib.Scraper):
    def __init__(self, *args, **kwargs):
        cache_storage = kwargs.pop('cache_storage')

        super().__init__(*args, **kwargs)
        if cache_storage:
            self.cache_storage = cache_storage
            self.cache_write_only = False
    

    def scrape(self):
        
        # Scrape the committee listing page for a list of committees with
        # scrapable events.
        response = self.get("https://docs.house.gov/Committee/Committees.aspx")
        committee_search = lxml.etree.HTML(response.text)

        committee_ids = committee_search.xpath('//option/@value')
        committee_ids = (id for id in committee_ids if id != '0')

        seen_meetings = set()
        for cmte in committee_ids:
        
            response = self.get("https://docs.house.gov/Committee/RSS.ashx",
                                params={'Code': cmte})

            rss = feedparser.parse(response.content)

            for item in rss['entries']:
                try:
                    xml_link, = (link for link in item['links'] if link['type'] == 'text/xml')
                except ValueError:
                    continue
                response = self.get(xml_link['url'])
                xml = lxml.etree.fromstring(response.content)

                meeting_id = xml.attrib['meeting-id']
                if meeting_id in seen_meetings:
                    continue
                else:
                    seen_meetings.add(meeting_id)
                yield xml_link['url'], xml
