Here's the updated `README.md`:

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
logedit [current_version] [changelog_file]
```

The `current_version` parameter can be used to specify both the old and new version in the format `old_version:new_version`. If only the new version is provided, Logedit will get the most recent version tag in your git repository as the old version.

The `changelog_file` is the path to your `CHANGELOG.md` file.

If you're generating a changelog for version `0.2` with version `0.1` as the old version and your `CHANGELOG.md` is in the same directory, you would use the command:

```bash
logedit 0.1:0.2 CHANGELOG.md
```

If you only provide the new version `0.2`:

```bash
logedit 0.2 CHANGELOG.md
```

## How it Works

Logedit retrieves all commits between the old and new versions specified. It then uses OpenAI's GPT-3.5-turbo to summarize each commit. 

Next, it feeds the tail of your current `CHANGELOG.md` file, the new version, and the commit summaries to GPT-3.5-turbo (or GPT-4 if specified) and generates a changelog entry in the same format as your existing `CHANGELOG.md`.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)