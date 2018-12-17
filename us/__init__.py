# encoding=utf-8
from pupa.scrape import Jurisdiction, Organization
from .events import UsEventScraper
from .people import UsPersonScraper
from .committees import UsCommitteeScraper

from pathlib import Path
import yaml


class Us(Jurisdiction):
    division_id = "ocd-division/country:us"
    classification = "legislature"
    name = "United States of America"
    url = "https://www.congress.gov/"
    scrapers = {
        "events": UsEventScraper,
        "committees": UsCommitteeScraper,
    }

    def get_organizations(self):

        legislature = Organization(name='United States Congress',
                                   classification="legislature")
        upper = Organization('United States Senate',
                             classification='upper',
                             parent_id=legislature._id)
        lower = Organization('United States House of Representatives',
                             classification='lower',
                             parent_id=legislature._id)

        yield legislature
        yield upper
        yield lower


    def _posts(self, upper, lower):
        current_path = Path(__file__)
        legislator_path = current_path.parent / 'congress-legislators/legislators-historical.yaml'
        

        with legislator_path.open() as f:
            legislators = yaml.load(f, Loader=yaml.CLoader)


        house_posts = set()
        senate_posts = set()
        for legislator in legislators:
            if all(term['end'] < '1970' for term in legislator['terms']):
                continue

            for term in legislator['terms']:
                
                if term['type'] == 'rep':
                    house_posts.add((term['state'], term['district']))
                elif term['type'] == 'sen':
                    senate_posts.add((term['state'], term['class']))
                else:
                    print(term)
                    raise

        for state, district in house_posts:
            if district:
                lower.add_post(
                    "{state}, District {district}".format(state=state,
                                                          district=district),
                    'Representative',
                    division_id='ocd-division/country:us/state:{state}/cd:{district}'.format(state=state.lower(), district=district))
            else:
                lower.add_post(
                    "{state}, At Large".format(state=state),
                    'Representative',
                    division_id='ocd-division/country:us/state:{state}'.format(state=state.lower()))
                

        for state, klass in senate_posts:
            upper.add_post(
                "{state}, Class {klass}".format(state=state,
                                                klass=klass),
                "Senator",
                division_id='ocd-division/country:us/state:{state}'.format(state=state.lower()))
