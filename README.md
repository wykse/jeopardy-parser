# jeopardy-parser

Parse Jeopardy clues and answers from [J! Archive](https://j-archive.com/). A csv file will be outputted for each game in an `output` directory.

## Installation

```
pip install -r requirements.txt
```

## Usage

Clone repo and change to project directory...

```
cd .\jeopardy-parser\
```

Run `seasons.py` to get seasons and create `_metadata.json` that includes games by season...

```
python .\jeopardy_parser\seasons.py
```

then run `clues.py` to get all clues for a game in a csv file.

```
python .\jeopardy_parser\clues.py
```

## TODO
- Add cli and options to download a subset of games
