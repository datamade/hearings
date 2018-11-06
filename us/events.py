from pupa.scrape import Scraper
from pupa.scrape import Event
from pupa.utils import _make_pseudo_id

import string
import datetime
import collections
import pprint
import re

import govinfo
import pytz
import xmltodict

from .house import HouseCommittee

API_KEY = 'E88VmdJAEOaI9xk4e2SHhsxBTP508sPSGH3aRT7j'

class UsEventScraper(govinfo.GovInfo, Scraper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers['X-Api-Key'] = API_KEY

    def _meeting_type(self, extension):
        meeting_code = extension.get('type')
        if meeting_code is None:
            return None

        codes_to_types = {'G': 'Hearing',
                          'T': 'Treaty Hearing',
                          'AU': 'Authorization Hearing',
                          'F': 'Field Hearing',
                          'O': 'Oversight Hearing',
                          'AP': 'Appropriations',
                          'M': 'Markup Session',
                          'N': 'Nomination Hearing'}

        return codes_to_types[meeting_code]
                

    def scrape(self, start_time=None):


        multi_part = collections.defaultdict(dict)

        if start_time is None:
            start_time = datetime.datetime(2018, 6, 5, 0, 0, tzinfo=pytz.utc)

        dupes = {}
        uniq = {}

        for i, hearing in enumerate(self.congressional_hearings(start_time)):
            package_id = hearing['packageId']
            package_num, = re.findall('\d+$', package_id)

            # For appropriations hearings, the committees tend to
            # publish portions of the hearings as they are completed,
            # and then the final hearing are usually compiled,
            # printed, and added to the repository at the request of
            # the Committee.
            #
            # packages with 8 digits after hrg are the in-process
            # version
            #
            # There could be some time between the in-process and
            # final packages. Publication of hearings is the purview
            # of the committee.
            #
            # https://github.com/usgpo/api/issues/21#issuecomment-435926223
            if len(package_num) == 8:
                continue

            mods_link = hearing['download']['modsLink']
            response = self.get(mods_link)
            mods = xmltodict.parse(response.content)
            extension = collections.ChainMap(*mods['mods']['extension'])

            granule_class = extension.get('granuleClass', 'boo')
            if granule_class == 'ERRATA':
                continue


            meeting_type = self._meeting_type(extension)
            if meeting_type is None:
                continue
            
            held_date = extension['heldDate']
            if type(held_date) is list:
                start_date = min(held_date)
            else:
                start_date = held_date

            event = Event(name=self._title(mods),
                          start_date=start_date,
                          classification=meeting_type,
                          location_name='unknown')
            if not event.name:
                continue

            for committee_d in self._unique(extension.get('congCommittee', [])):
                names = committee_d['name']
                committee_name = self._name_type(names,
                                                 'authority-standard')
                if committee_name is None:
                    committee_name = self._name_type(names,
                                                     'authority-short')

                if committee_d['@chamber'] == 'H':
                    committee_name = 'House ' + committee_name
                elif committee_d['@chamber'] == 'S':
                    committee_name = 'Senate ' + committee_name

                try:
                    thomas_id = committee_d['@authorityId'].upper()
                except KeyError:
                    thomas_id = None

                sub_committees = self._subcommittees(committee_d)
                if sub_committees:
                    for sub_committee_d in sub_committees:
                        sub_committee_name = sub_committee_d['name']['#text']
                        sub_committee_name = sub_committee_name.strip(string.punctuation)
                        sub_committee_id = _make_pseudo_id(name=sub_committee_name,
                                                           parent__identifiers__identifier=thomas_id)
                        ret = {"name": sub_committee_name,
                               "entity_type": 'organization',
                               "note": 'host',
                               "organization_id": sub_committee_id,
                               }
                        event.participants.append(ret)

                else:
                    if thomas_id:
                        ret = {"name": committee_name,
                               "entity_type": 'organization',
                               "note": 'host',
                               "organization_id": _make_pseudo_id(identifiers__identifier=thomas_id)}
                        event.participants.append(ret)
                    else:
                        event.add_committee(committee_name, note='host')


            links = mods['mods']['location']['url']                
            for link in self._unique(links):
                if link['@displayLabel'] == 'Content Detail':
                    event.add_source(link['#text'],
                                     note='web')
                elif link['@displayLabel'] == 'HTML rendition':
                    event.add_document('transcript',
                                       link['#text'],
                                       media_type='text/html')
                elif link['@displayLabel'] == 'PDF rendition':
                    event.add_document('transcript',
                                       link['#text'],
                                       media_type='application/pdf')
                
            event.add_source(mods_link, note='API')

            if 'partNumber' in extension:
                multi_part[event.name][extension['partNumber']] = event
                continue

            if 'volumeNumber' in extension:
                multi_part[event.name][extension['volumeNumber']] = event
                continue

            self._unique_event(uniq, event, dupes)

            if i > 100:
                break

        for parts in multi_part.values():
            parts = iter(parts.items())
            part_number, event = next(parts)
            sources = event.sources
            event.sources = []
            for source in sources:
                event.add_source(source['url'],
                                 note=source['note'] + ', part {}'.format(part_number))

            for part_number, other_event in parts:
                for source in other_event.sources:
                    event.add_source(source['url'],
                                     note=source['note'] + ', part {}'.format(part_number))

            self._unique_event(uniq, event, dupes)

        self._house_docs(uniq)

        for event in uniq.values():
            yield event

    def _unique_event(self, uniq, event, dupes):
        event_key = (event.name, event.start_date)
        other_event = uniq.get(event_key)

        if other_event:
            other_package_num = self._package_num(other_event)
            this_package_num = self._package_num(event)

            if this_package_num < other_package_num:
                uniq[event_key] = event

            if event_key in dupes:
                dupes[event_key].append(self._api_url(event))
            else:
                dupes[event_key] = [self._api_url(other_event),
                                    self._api_url(event)]
        else:
            uniq[event_key] = event

    def _house_docs(self, uniq):
        _house_docs ={}

        house_scraper = HouseCommittee(cache_storage=self.cache_storage,
                                       requests_per_minute=self.requests_per_minute)
        for link, hearing_xml in house_scraper.scrape():
            meeting_title, = hearing_xml.xpath('//meeting-title/text()')
            start_date, = hearing_xml.xpath('//meeting-date/calendar-date/text()')

            try:
                room, = hearing_xml.xpath('//room/text()')
            except ValueError:
                location = 'unknown'
            else:
                location = '{} {}'.format(hearing_xml.xpath('//building/text()')[0],
                                          room)

            meeting_title = meeting_title.upper()
            event = uniq.get((meeting_title.upper(), start_date))

            if event is not None:
                event.location = {"name": location, "note": "", "coordinates": None}
                event.add_source(link, note='docs.house.gov XML')
                self._add_house_docs(event, hearing_xml)

            else:

                event = Event(name=meeting_title[:1000],
                              start_date=start_date,
                              location_name=location)

                event.add_source(link, note='docs.house.gov XML')

                for sub_committee in hearing_xml.xpath('//subcommittees/committee-name'):
                    name, = sub_committee.xpath('.//text()')
                    thomas_id = sub_committee.attrib['parent-id']
                    participant =  {"name": name,
                                    "entity_type": 'organization',
                                    "note": 'host',
                                    "organization_id": _make_pseudo_id(name=name,
                                                                       parent__identifiers__identifier=thomas_id),
                               }
                    event.participants.append(participant)

                for committee in hearing_xml.xpath('//committees/committee-name'):
                    name, = committee.xpath('.//text()')
                    thomas_id = committee.attrib['id']
                    participant =  {"name": name,
                                    "entity_type": 'organization',
                                    "note": 'host',
                                    "organization_id": _make_pseudo_id(identifiers__identifier=thomas_id),
                    }

                    event.participants.append(participant)

                self._add_house_docs(event, hearing_xml)

                uniq[(meeting_title, start_date)] = event


    def _add_house_docs(self, event, hearing_xml):
        media_type = {'PDF': 'application/pdf',
                      'XML': 'text/xml'}

        seen_docs = set()
        for doc in hearing_xml.xpath('//meeting-document'):
            if doc.attrib['type'] in {'BR', 'SD', 'FR'}:
                continue

            try:
                doc_description, = doc.xpath('.//description/text()')
            except ValueError:
                continue

            for doc_file in doc.xpath('.//files/file'):

                doc_url = doc_file.attrib['doc-url']
                if doc_url in seen_docs:
                    continue
                else:
                    seen_docs.add(doc_url)

                doc_mime_type = media_type[doc_file.attrib['doc-type']]
                event.add_document(doc_description[:300],
                                   doc_url,
                                   media_type=doc_mime_type)


    def _package_num(self, event):
        api_url = self._api_url(event)
        package_id = api_url.split('/')[-2]
        package_num, = re.findall('\d+$', package_id)
        return package_num

    def _api_url(self, event):
        try:
            api_source, = (source for source in event.sources if source['note'] == 'API')
        except ValueError:
            api_source = min((source for source in event.sources if source['note'].startswith('API')), key=lambda source: source['url'])

        return api_source['url']


    def _name_type(self, names, name_type):
        if type(names) is not list:
            return names['#text']
        chosen_name = [name for name in names
                       if name['@type'] == name_type]

        if not chosen_name:
            return None

        if len(chosen_name) == 1:
            chosen_name, = chosen_name
            if '#text' not in chosen_name:
                return None
            else:
                return chosen_name['#text']

        else:
            return max((name['#text'] for name in chosen_name),
                       key=len)
                            

    def _unique(self, iterable):
        if type(iterable) is not list:
            iterable = [iterable]

        seen = []
        for each in iterable:
            if each not in seen:
                yield each
                seen.append(each)


    def _title(self, mods):
       title_info = mods['mods']['titleInfo']
       for each in title_info:
           if 'title' in each:
               title = each['title']
               if title:
                   title = title[:1000]
               return title
                              
    def _subcommittees(self, committee_d):
        subcommittees = []
        if 'subCommittee' in committee_d:
            sub_committees = self._unique(committee_d['subCommittee'])
            for sub_committee_d in sub_committees:
                if '#text' not in sub_committee_d['name']:
                    continue
                else:
                    subcommittees.append(sub_committee_d)

        return subcommittees
