# encoding=utf-8
from pupa.scrape import Jurisdiction, Organization
from .events import UsEventScraper
from .people import UsPersonScraper


class Us(Jurisdiction):
    division_id = "ocd-division/country:us"
    classification = "legislature"
    name = "United States of America"
    url = "https://www.congress.gov/"
    scrapers = {
        "events": UsEventScraper,
        #"people": UsPersonScraper,
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
