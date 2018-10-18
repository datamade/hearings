from pupa.scrape import Scraper
from pupa.scrape import Organization

from pathlib import Path
import yaml

CONGRESSES = {
    84: '1955-01-03',
    85: '1957-01-03',
    86: '1959-01-03',
    87: '1961-01-03',
    88: '1963-01-03',
    89: '1965-01-03',
    90: '1967-01-03',
    91: '1969-01-03',
    92: '1971-01-03',
    93: '1973-01-03',
    94: '1975-01-03',
    95: '1977-01-03',
    96: '1979-01-03',
    97: '1981-01-03',
    98: '1983-01-03',
    99: '1985-01-03',
    100: '1987-01-03',
    101: '1989-01-03',
    102: '1991-01-03',
    103: '1993-01-03',
    104: '1995-01-03',
    105: '1997-01-03',
    106: '1999-01-03',
    107: '2001-01-03',
    108: '2003-01-03',
    109: '2005-01-03',
    110: '2007-01-03',
    111: '2009-01-03',
    112: '2011-01-03',
    113: '2013-01-03',
    114: '2015-01-03',
    115: '2017-01-03',
    116: '2019-01-03',}

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

            start, end = duration(committee)

            c.founding_date = start
            if end:
                c.dissolution_date = end

            c.add_identifier(committee['thomas_id'] + '00',
                             scheme='thomas_id')

            if 'house_committee_id' in committee:
                c.add_identifier(committee['house_committee_id'],
                                 scheme='house_committee_id')
            if 'senate_committee_id' in committee:
                c.add_identifier(committee['senate_committee_id'],
                                 scheme='senate_committee_id')


            c.add_source('https://github.com/unitedstates/congress-legislators/blob/master/committees-historical.yaml')
            
            for name in committee['names'].values():
                c.add_name(name)


            yield c


            for subcommittee in committee.get('subcommittees', []):
                sc = Organization('Subcommittee on ' + subcommittee['name'],
                                  classification='committee',
                                  parent_id=c)

                start, end = duration(subcommittee)

                sc.founding_date = start
                if end:
                    sc.dissolution_date = end


                thomas_id = (committee['thomas_id']
                             + subcommittee['thomas_id'])
                sc.add_identifier(thomas_id,
                                  scheme='thomas_id')
                

                sc.add_source('https://github.com/unitedstates/congress-legislators/blob/master/committees-historical.yaml')

                if thomas_id == 'SSJU12':
                    sc.add_identifier('SSJU15',
                                      scheme='thomas_id')
                elif thomas_id == 'SSJU15':
                    continue
                if 'Oversight and Investigations' in sc.name:
                    print(thomas_id)
                    #input()

                for name in subcommittee['names'].values():
                    sc.add_name(name)

                yield sc

def duration(committee):
    first_congress = min(committee['congresses'])
    last_congress = max(committee['congresses'])
    if last_congress == 115:
        end = None
    else:
        end = CONGRESSES[last_congress + 1]
    
    return CONGRESSES[first_congress], end
                         
