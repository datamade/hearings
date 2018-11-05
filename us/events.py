from pupa.scrape import Scraper
from pupa.scrape import Event
from pupa.utils import _make_pseudo_id

import datetime
import collections
import pprint
import re

import govinfo
import pytz
import xmltodict

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

        uniq = {}

        for i, hearing in enumerate(self.congressional_hearings(start_time)):
            mods_link = hearing['download']['modsLink']
            response = self.get(mods_link)
            mods = xmltodict.parse(response.content)
            extension = collections.ChainMap(*mods['mods']['extension'])

            granule_class = extension.get('granuleClass', 'boo')
            if granule_class == 'ERRATA':
                continue
            elif granule_class not in {'OTHERPART', 'FIRSTPART', 'boo'}:
                raise

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
                parent, sub_committees = self._subcommittees(committee_d)
                if sub_committees:
                    for sub_committee_d in sub_committees:
                        committee_name = sub_committee_d['name']['#text']
                        sub_committee_id = _make_pseudo_id(name=committee_name,
                                                           parent__name=parent)
                        ret = {"name": committee_name,
                               "entity_type": 'organization',
                               "note": 'host',
                               "organization_id": sub_committee_id,
                               }
                        event.participants.append(ret)

                else:
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
                    elif committee_d['@chamber'] != 'J':
                        import pdb
                        pdb.set_trace()
                    event.add_committee(committee_name,
                                        note='host')


            # for witness in extension.get('witness', []):
            #     event.add_person(witness,
            #                      note='witness')

            # for congress_person in self._unique(extension.get('congMember', [])):
            #     names = congress_person['name']
            #     name = self._name_type(names,
            #                            'authority-fnf')
                
            #     event.add_person(name,
            #                      note='committee member')

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

            self._unique_event(uniq, event)

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

            self._unique_event(uniq, event)

        for event in uniq.values():
            yield event

    def _unique_event(self, uniq, event):
        event_key = (event.name, event.start_date)
        other_event = uniq.get(event_key)

        if other_event:
            other_package_num = self._package_num(other_event)
            this_package_num = self._package_num(event)

            if this_package_num < other_package_num:
                uniq[event_key] = event

        else:
            uniq[event_key] = event


    def _package_num(self, event):
        try:
            api_source, = (source for source in event.sources if source['note'] == 'API')
        except ValueError:
            api_source = min((source for source in event.sources if source['note'].startswith('API')), key=lambda source: source['url'])

        api_url = api_source['url']
        package_id = api_url.split('/')[-2]
        package_num, = re.findall('\d+$', package_id)
        return package_num


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

        if subcommittees:
            parent_names = committee_d['name']
            parent_name = self._name_type(parent_names,
                                          'authority-standard')
            return parent_name, subcommittees
        else:
            return None, []
