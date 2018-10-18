from pupa.scrape import Scraper
from pupa.scrape import Event

import govinfo
import datetime
import pytz
import xmltodict
import pprint
import collections

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

        for i, hearing in enumerate(self.congressional_hearings(start_time)):
            mods_link = hearing['download']['modsLink']
            response = self.get(mods_link)
            mods = xmltodict.parse(response.content)
            extension = collections.ChainMap(*mods['mods']['extension'])

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
                sub_committees = self._subcommittees(committee_d)
                if sub_committees:
                    for sub_committee_d in sub_committees:
                        committee_name = sub_committee_d['name']['#text']
                        event.add_committee(committee_name,
                                            note='host')

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

            yield event

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

            yield event

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
               return each['title'][:1000]
                              
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
