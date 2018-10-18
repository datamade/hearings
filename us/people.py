from pupa.scrape import Scraper
from pupa.scrape import Person

from pathlib import Path
import yaml

class UsPersonScraper(Scraper):

    def scrape(self):
        current_path = Path(__file__)
        legislator_path = current_path.parent / 'congress-legislators/legislators-historical.yaml'

        with legislator_path.open() as f:
            legislators = yaml.load(f, Loader=yaml.CLoader)

        for legislator in legislators:
            if all(term['end'] < '1970' for term in legislator['terms']):
                continue
            
            l = Person(name = ' '.join((legislator['name']['first'],
                                        legislator['name']['last'])),
                       birth_date=legislator['bio'].get('birthday', ''),
                       gender=legislator['bio']['gender'])


            parties = set()
            for term in legislator['terms']:
                state = term['state']
                parties.add(term['party'])
                
                if term['type'] == 'rep':
                    role = 'Representative'
                    district_name = self._district_name(state,
                                                        term['district'])
                    chamber='lower'
                else:
                    role = "Senator"
                    district_name = "{state}, Class {klass}".format(state=state,
                                                                    klass=term['class'])
                    chamber='upper'

                l.add_term(role,
                           chamber,
                           district=district_name,
                           start_date=term['start'],
                           end_date=term['end'])

            for party in parties:
                l.add_party(party)


            for scheme, identifier in legislator['id'].items():
                l.add_identifier(str(identifier), scheme=scheme)

            l.add_source('https://github.com/unitedstates/congress-legislators/blob/master/legislators-historical.yaml')


            yield l


    def _district_name(self, state, district):
        if district:
            district_name = "{state}, District {district}".format(state=state,
                                                                  district=district)
        else:
            district_name = "{state}, At Large".format(state=state)

        return district_name
