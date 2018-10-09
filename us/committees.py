from pupa.scrape import Scraper
from pupa.scrape import Organization

from pathlib import Path
import yaml

class UsCommitteeScraper(Scraper):

    def scrape(self):
        current_path = Path(__file__)
        committee_path = current_path.parent / 'congress-legislators/committees-historical.yaml'

        with committee_path.open() as f:
            committees = yaml.load(f, Loader=yaml.CLoader)

        for committee in committees:
            if committee['type'] == 'house':
                chamber = 'lower'
            elif committee['type'] == 'senate':
                chamber = 'upper'
            else:
                print(committee)
                raise

            c = Organization(committee['name'],
                             classification='committee',
                             chamber=chamber)

            c.add_identifier(committee['thomas_id'],
                             scheme='thomas_id')

            if 'house_committee_id' in committee:
                c.add_identifier(committee['house_committee_id'],
                                 scheme='house_committee_id')
            if 'senate_committee_id' in committee:
                c.add_identifier(committee['senate_committee_id'],
                                 scheme='senate_committee_id')


            c.add_source('https://github.com/unitedstates/congress-legislators/blob/master/committees-historical.yaml')

            yield c


            for subcommittee in committee.get('subcommittees', []):
                sc = Organization(subcommittee['name'],
                                  classification='committee',
                                  parent_id=c)
                
                sc.add_identifier(committee['thomas_id'],
                                  scheme='thomas_id')
                

                sc.add_source('https://github.com/unitedstates/congress-legislators/blob/master/committees-historical.yaml')

                yield sc
