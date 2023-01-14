import logging
import re

from bs4 import BeautifulSoup


def to_lower_underscore(s: str) -> str:
    """Convert string to lowercase and replace white space with a single underscore.
    And only keep alphanumeric chars.

    Args:
        s (str): String to convert

    Returns:
        str: Lowercased alphanumeric string with underscores
    """    
    # Replace white space with underscore
    new_s = re.sub(r"\s+", "_", s.strip())

    # Replace any non alphanumeric char with nothing, and lowercase
    new_s = re.sub(r"[^a-zA-Z|\d|_]+", "", new_s).lower()

    return new_s


def stringify_contents(content: str, tag: str) -> str:
    """Stringify the contents of a tag.

    Tags sometimes include html inside the tag (e.g., an a tag within a td tag)
    along with text. Need to only keep the text from the tag and any tags inside td.

    Args:
        content (str): Contents of tag.
        tag (str): Tag. E.g., "td"

    Returns:
        str: String of all text in tag's content.
    """
    soup = BeautifulSoup(content, "lxml")

    contents_text = []
    for content in soup.find(tag).contents:
        contents_text.append(content.text)

    return "".join(contents_text)


def stringify_contents_with_newline(content: str) -> str:
    soup = BeautifulSoup(content, "lxml")

    # Replace br tags with newline ('\n')
    for _ in soup.findAll("br"):
        soup.br.replace_with("\n")

    return soup.text


def config_logger(path: str) -> None:
    """Setup the logger."""

    logging.basicConfig(
        level=logging.DEBUG,
        filename=path,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
