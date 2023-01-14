import json
import logging
import time
from datetime import datetime
from pathlib import Path

import requests
from attrs import asdict, define, field
from helpers import config_logger
from parsel import Selector
from tqdm import tqdm


@define
class Season:
    title: str
    url: str
    count: int = field(init=False)
    game_urls: list
    accessed_at: str = field(init=False)

    def __attrs_post_init__(self):
        self.count = len(self.game_urls)
        self.accessed_at = datetime.now().isoformat()


@define
class Metadata:
    title: str = r"Jeopardy clue and answers from J! Archive"
    url: str = r"https://j-archive.com/"
    seasons: list[Season] = None
    accessed_at: str = field(init=False)

    def __attrs_post_init__(self):
        self.accessed_at = datetime.now().isoformat()

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(asdict(self), f)
            logging.debug(f"Saved metadata file.")


def get_seasons_urls() -> dict[str, str]:
    logging.info("Get url for each season landing page...")
    # Url for all seasons
    LIST_SEASONS_URL = r"https://j-archive.com/listseasons.php"

    response = requests.get(LIST_SEASONS_URL)

    selector = Selector(response.text)

    all_seasons_urls = {}

    # All a tag selectors containing containing a season query param
    a_selectors = selector.xpath("//a[contains(@href, 'showseason.php?season=')]")

    # Stringify the contents of each a tag
    for a_selector in a_selectors:
        # link_text = stringify_contents(a_selector.get(), "a")
        link_text = Selector(a_selector.get()).xpath("string()").get()
        if link_text not in ["[current season]", "[last season]"]:
            href = a_selector.attrib["href"]
            all_seasons_urls[link_text] = f"https://j-archive.com/{href}"
            logging.info(f"a_text={link_text}, href={href}")

    return all_seasons_urls


def get_game_urls(season_url: str) -> list:
    """Get a list of game urls for the provided season.

    Args:
        season_url (str): Url to page for all of the season's games

    Returns:
        list: A list of all game urls for the provided season
    """
    response = requests.get(season_url)

    selector = Selector(response.text)

    all_game_urls = []

    # All a tag selectors containing containing a game id query param
    a_selectors = selector.xpath(
        "//td[@align='left']/a[contains(@href, 'showgame.php?game_id=')]"
    )

    # Stringify the contents of each a tag
    for a_selector in a_selectors:
        all_game_urls.append(a_selector.attrib["href"])

    return all_game_urls


def main():
    # Get path of file
    path = Path(__file__)

    # Setup logger
    config_logger(path.parents[1] / f"_jeopardy_{path.stem}.log")

    # Get url for each season
    seasons_urls = get_seasons_urls()
    logging.debug(f"Number of seasons: {len(seasons_urls)}")

    # Hold seasons
    seasons = []

    # Get url for each season's games
    for season in tqdm(seasons_urls.keys()):
        logging.debug(f"Starting season: {season}")
        game_urls = get_game_urls(seasons_urls[season])
        logging.debug(f"Season: {season}, {len(game_urls)} games archived")

        seasons.append(
            Season(
                title=season,
                url=seasons_urls[season],
                game_urls=game_urls,
            )
        )

        # Sleep before another request is made
        time.sleep(2)

    # Save metadata file as json
    Metadata(seasons=seasons).to_json(path.parents[1] / "_metadata.json")


if __name__ == "__main__":
    main()
