# Logedit

Logedit is a Python utility that auto-generates changelogs from git commits using OpenAI's APIs.

## Installation

You can install Logedit from PyPI:

```bash
pip install logedit
```

You'll also need to set your OpenAI API key:

```bash
export OPENAI_API_KEY='your-api-key-here'
```

## Usage

You can specify the version, the path to the changelog file, and whether to append the new entry to the original changelog file using the `--version`, `--changelog`, and `--append` arguments, respectively:

```bash
logedit --version [current_version] --changelog [changelog_file] --append
```

The `--version` parameter can be used to specify both the old and new version in the format `old_version:new_version`. If only the new version is provided, Logedit will get the most recent version tag in your git repository as the old version.

The `--changelog` parameter is the path to your `CHANGELOG.md` file.

If `--append` is provided, the new changelog entry will be automatically appended to the specified changelog file.

If you're generating a changelog for version `0.2` with version `0.1` as the old version and your `CHANGELOG.md` is in the same directory, you would use the command:

```bash
logedit --version 0.1:0.2 --changelog CHANGELOG.md --append
```

If you only provide the new version `0.2`, Logedit will consider the most recent tagged release in your repository as the old version:

```bash
logedit --version 0.2 --changelog CHANGELOG.md --append
```

Shorter aliases `-v` for version, `-c` for changelog, and `-a` for append are also available:

```bash
logedit -v 0.2 -c CHANGELOG.md -a
```

## How it Works

Logedit retrieves all commits between the old and new versions specified. It then uses OpenAI's GPT-3.5-turbo to summarize each commit. 

Next, it feeds the tail of your current `CHANGELOG.md` file, the new version, and the commit summaries to GPT-3.5-turbo (or GPT-4 if specified) and generates a changelog entry in the same format as your existing `CHANGELOG.md`.

If the `--append` option is used, the new entry is automatically added to your changelog file.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)