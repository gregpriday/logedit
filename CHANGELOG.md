# Changelog

## [0.1.0] - 2023-05-29

### Added
- Implemented parallel processing of commit summaries using `ThreadPoolExecutor` to improve speed.
- Added backoff and retries to improve reliability during commit summarization.
- Integrated TikToken to limit the number of tokens passed to GPT-3.5, ensuring a maximum of 2048 tokens.

### Changed
- Moved messages into a separate JSON file for easier management of prompt text.
- Updated file handling to use context managers for proper file closing and avoiding resource leaks.

### Fixed
- Added error handling for missing `OPENAI_API_KEY` environment variable, raising a `ValueError` if not set.

## [0.0.1] - 2023-05-28

### Added
- Initial release of the Logedit package.
- Implemented core functionality for retrieving commit history between two version tags.
- Added capability to use OpenAI's GPT-3.5-turbo to summarize each commit.
- Functionality to feed the tail of the current `CHANGELOG.md` file, the new version, and the commit summaries to GPT-3.5-turbo (or GPT-4 if specified), and generate a changelog entry in the same format as the existing `CHANGELOG.md`.
- Introduced `--version`, `--changelog`, and `--append` arguments to specify version, path to changelog file, and whether to append the new entry to the original changelog file, respectively.
- Added feature to automatically append the new changelog entry to the specified changelog file if `--append` is provided.