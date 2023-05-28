# Logedit

Logedit is a Python utility that auto-generates changelogs from git commits using OpenAI's APIs.

## Installation

You can install Logedit from PyPI:

```
pip install logedit
```

You'll also need to set your OpenAI API key:

```
export OPENAI_API_KEY='your-api-key-here'
```

## Usage

```bash
python -m logedit [current_version] [changelog_file]
```

The `current_version` is the version of the software you're creating a changelog for. The `changelog_file` is the path to your `CHANGELOG.md` file.

If you're generating a changelog for version `0.2` and your `CHANGELOG.md` is in the same directory, you would use the command:

```bash
python -m logedit 0.2 CHANGELOG.md
```

## How it Works

Logedit gets the most recent version tag in your git repository and then retrieves all commits since that version. It then uses OpenAI's GPT-3.5-turbo to summarize each commit. 

Next, it feeds the tail of your current `CHANGELOG.md` file, the current version, and the commit summaries to GPT-3.5-turbo (or GPT-4 if specified) and generates a changelog entry in the same format as your existing `CHANGELOG.md`.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)