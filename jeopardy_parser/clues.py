import asyncio
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import aiohttp
import pandas as pd
from attrs import asdict, define
from helpers import (
    config_logger,
    create_directory,
    stringify_contents_with_newline,
    to_lower_underscore,
)
from parsel import Selector


@define
class Clue:
    show_num: str
    air_date: str
    round: str
    category: str
    category_comment: str
    value: str
    daily_double: bool
    clue: str
    correct_response: str
    clue_id: str
    url: str


def get_jarchive_game_id(url: str) -> str:
    return parse_qs(urlparse(url).query)["game_id"][-1]


def list_game_ids_in_dir(path: str) -> list[str]:
    """Get a list of game ids in directory.
    E.g., "2022-10-16-4-primetime_celebrity_jeopardy-7472-output.csv"
    "2023-01-05-9-primetime_celebrity_jeopardy-7635-output.csv"

    Returns ["7472", "7635"]

    Args:
        path (str): Path to directory

    Returns:
        list[str]: List of game ids in directory
    """
    p = Path(path)
    files = list(p.iterdir())
    game_ids = [f.stem.split("-")[-2] for f in files if f.suffix == ".csv"]
    return game_ids


def is_daily_double(clue_value: str) -> bool:
    """Checks if the clue is a Daily Double. Check's clue_value text.

    Args:
        clue_value (str): clue_value text.

    Returns:
        bool: True if Daily Double else False.
    """
    if re.match(r"DD", clue_value) is None:
        return False
    else:
        return True


def get_category(clue_id: str, categories: dict[str, list[tuple]]) -> tuple:
    """Return a tuple of category name and category comments, i.e., (name, comments).

    Args:
        clue_id (str): Clue id, e.g., "clue_J_1_5", "clue_DJ_6_5", "clue_FJ"
        categories (dict[str, list[tuple]]):
            e.g. {"jeopardy_round": [(<category_name>, <category_comments>)]}

    Returns:
        tuple: A tuple containing category name and category comments.
            E.g., ("MATH TO ROMAN NUMERALS TO INITIALS TO NAMES",
                "(Alex: Let me give you an example: 1,000 + 100 to this
                "Wrecking Ball" singer--1,000 and 100, that's MC--Miley
                Cyrus. We will need both first and last names.)")
    """

    # Index 1 is round, index 2 is category column (starting at 1)
    clue_id_split = clue_id.split("_")

    # Get category by round
    match clue_id_split[1]:
        case "J":
            # Category column starts 1, minus 1 to get the index
            return categories["jeopardy_round"][int(clue_id_split[2]) - 1]
        case "DJ":
            return categories["double_jeopardy_round"][int(clue_id_split[2]) - 1]
        case "TJ":
            return categories["triple_jeopardy_round"][int(clue_id_split[2]) - 1]
        case _:
            return categories["final_jeopardy_round"][0]


async def get_clues(name: str, work_queue, path: str):
    async with aiohttp.ClientSession() as session:
        while not work_queue.empty():
            season_url = await work_queue.get()
            logging.info(
                f"Task {name} getting {season_url['season']}: {season_url['url']}"
            )
            print(f"Task {name} getting {season_url['season']}: {season_url['url']}")

            async with session.get(season_url["url"]) as response:
                html = await response.text()

                selector = Selector(html)

                clues = []

                # Get a list of all rounds
                rounds = selector.xpath(
                    "//div[contains(@id, 'jeopardy_round')]/@id"
                ).getall()

                categories = {round: [] for round in rounds}

                title = selector.xpath("//head/title/text()").get()
                show_num = re.search(r"(?<=#)\d*(?=,)", title).group()
                air_date = re.search(r"\d{4}-\d{2}-\d{2}", title).group()

                # Get category names and category comments for each round
                for round in categories.keys():
                    category_list = selector.xpath(
                        f"//div[@id='{round}']/descendant::td[@class='category']"
                    )

                    # Append category name and comments
                    for category in category_list:
                        category_name = category.xpath(
                            "string(.//td[@class='category_name'])"
                        ).get()
                        category_comments = category.xpath(
                            "string(.//td[@class='category_comments'])"
                        ).get()

                        categories[round].append((category_name, category_comments))

                    # Get all clues for the round
                    clue_selectors = selector.xpath(
                        f"//div[@id='{round}']/descendant::td[@class='clue']"
                    )

                    # For each clue, get clue text, id, and value
                    for clue_selector in clue_selectors:
                        # Get clue first because all rounds have a clue
                        # Get clue contents
                        clue_content = clue_selector.xpath(
                            ".//td[@class='clue_text']"
                        ).get()

                        # Continue to next item when there is no clue
                        if clue_content is None:
                            continue

                        # Replace all br with newline
                        clue_text = stringify_contents_with_newline(clue_content)

                        # Get clue id
                        clue_id = clue_selector.xpath(
                            ".//td[@class='clue_text']"
                        ).attrib["id"]

                        # Get clue value
                        clue_value = clue_selector.xpath(
                            ".//td[contains(@class, 'clue_value')]/text()"
                        ).get()

                        # If there is no value, assume it is not a daily double
                        if clue_value is None:
                            daily_double = False
                        else:
                            # Check if clue is a daily double
                            daily_double = is_daily_double(clue_value)

                            # Clean clue value; remove DD and any white space
                            clue_value = re.sub(r"DD:", "", clue_value).strip()

                        # Get response
                        # Response is added when an onmouseover event occurs
                        # Regex pattern to get response
                        correct_response_regex = re.compile(
                            r"(?<=<em class=.correct_response.>).*(?=</em>)"
                        )

                        # Get event function code
                        # Final round response is in a different tag than the other rounds
                        event_code = selector.xpath(
                            f"//div[contains(@onmouseover, '{clue_id}')]/@onmouseover"
                        ).get()

                        # Get response text from the function code in the div tag
                        correct_response_text = correct_response_regex.search(
                            event_code
                        ).group()

                        # Parse the correct response for the actual text. Sometimes the response has an i tag.
                        # Get text and all descendants, if any.
                        correct_response_text = (
                            Selector(correct_response_text).xpath("string()").get()
                        )

                        clue = Clue(
                            show_num=show_num,
                            air_date=air_date,
                            round=round,
                            category=get_category(clue_id, categories)[0],
                            category_comment=get_category(clue_id, categories)[1],
                            value=clue_value,
                            daily_double=daily_double,
                            clue=clue_text,
                            correct_response=correct_response_text,
                            clue_id=clue_id,
                            url=response.url,
                        )

                        clues.append(clue)
                        logging.info(clue)

            # Output to csv
            # TODO: use csv module instead of pandas
            df = pd.DataFrame.from_records([asdict(clue) for clue in clues])

            p = Path(path)

            file = f"{air_date}-{show_num}-{to_lower_underscore(season_url['season'])}-{get_jarchive_game_id(season_url['url'])}-output.csv"

            df.to_csv(p / file, index=False)

            await asyncio.sleep(2)


async def main():
    p = Path(__file__)
    output_path = p.parents[1] / "output"

    # Setup logger
    config_logger(p.parents[1] / f"_jeopardy_{p.stem}.log")
    logging.info(f"Starting {p.name}")

    # Create output directory
    create_directory(output_path)

    # Key game id, value is season and url
    game_urls: dict[dict[str, str]] = {}

    # Get game urls
    with open(p.parents[1] / "_metadata.json", "r") as f:
        metadata = json.load(f)
        for season in metadata["seasons"]:
            for url in season["game_urls"]:
                game_urls[get_jarchive_game_id(url)] = {
                    "season": season["title"],
                    "url": url,
                }

    # Game ids of the game urls
    gid_from_urls = set(game_urls.keys())

    # Game ids of the files already in output dir
    gids_from_dir = set(list_game_ids_in_dir(output_path))

    # Game ids of the game urls not already downloaded, i.e., download these games
    gids_to_download = gid_from_urls - gids_from_dir

    print(f"Getting clues for {len(gids_to_download)} game ids: {gids_to_download}")

    logging.info(
        f"Getting clues for {len(gids_to_download)} game ids: {gids_to_download}"
    )

    # Create the queue of work
    work_queue = asyncio.Queue()

    # Put gids to download in the queue
    for gid in gids_to_download:
        await work_queue.put(game_urls[gid])

    # Run the tasks
    await asyncio.gather(
        asyncio.create_task(get_clues("One", work_queue, output_path)),
        asyncio.create_task(get_clues("Two", work_queue, output_path)),
        asyncio.create_task(get_clues("Three", work_queue, output_path)),
    )


if __name__ == "__main__":
    asyncio.run(main())
