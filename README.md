# jeopardy-parser

Parse Jeopardy clues and answers from [J! Archive](https://j-archive.com/). A csv file will be outputted for each game.

## Installation

```
pip install -r requirements.txt
```

## Usage

Clone repo, change to project directory, and make an `output` directory...

```
cd .\jeopardy-parser\
mkdir output
```

Run the following to get seasons and create `_metadata.json` that includes games by season...

```
python .\jeopardy_parser\seasons.py
```

then run the following to get clues.

```
python .\jeopardy_parser\clues.py
```

## TODO
- Add cli and options to download a subset of games