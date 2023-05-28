import os
import re
import sys

import openai
from git import Repo, InvalidGitRepositoryError
from tqdm import tqdm
import argparse
from datetime import datetime

# initialize openai api
openai.api_key = os.getenv("OPENAI_API_KEY")

script_dir = os.path.dirname(os.path.abspath(__file__))


def summarize(text):
    system_message = open(os.path.join(script_dir, "./system/commit_summarizer.txt"), "r").read()
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Summarize the following commit details:\n\n{text}"}
        ],
        temperature=0.4
    )
    return completion.choices[0].message['content']


def main(current_version="HEAD", changelog_file="CHANGELOG.md", model="gpt-4", append=False):
    if current_version is None or changelog_file is None:
        print("Error: Missing required arguments: 'current_version' and 'changelog_file'")
        print("Usage: logedit [current_version] [changelog_file]")
        return

    try:
        repo = Repo(os.getcwd())
    except InvalidGitRepositoryError:
        print(
            f"The current directory ({os.getcwd()}) is not a valid Git repository. Please navigate to a Git repository and try again.")
        sys.exit(1)

    if ':' in current_version:
        previous_version, current_version = current_version.split(':')
    else:
        # get all tags in repo
        tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)

        # Filter for only tags that follow the format of a version number (with optional v prefix)
        version_tags = [tag for tag in tags if re.match(r"^v?(\d+\.)*\d+$", str(tag))]

        # find the most recent version
        previous_version = version_tags[-1] if version_tags else None

    print(f"Previous version is: {previous_version}")
    print(f"Current version is: {current_version}")

    # get commits between recent version and current version
    commits = list(repo.iter_commits(f'{previous_version}..HEAD'))

    print(f"Total commits: {len(commits)}")

    # loop over all commits and get summaries
    summaries = []
    for commit in tqdm(commits, desc="Summarizing commits"):
        diff = repo.git.diff(commit.parents[0].hexsha, commit.hexsha)
        text = commit.message + "\n" + diff
        summary = summarize(text)
        timestamp = commit.committed_datetime.isoformat()  # ISO 8601 format
        formatted_commit_info = f"Commit: {commit.hexsha[:6]}\nTimestamp: {timestamp}\nMessage: {commit.message}\nSummary: {summary}"
        summaries.append(formatted_commit_info)

    # read the tail of the current changelog file
    with open(changelog_file, 'r') as file:
        last_lines = file.readlines()[-40:]

    # generate a new changelog entry using OpenAI
    system_message = open(os.path.join(script_dir, "./system/changelog_writer.txt"), "r").read()
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user",
         "content": "Here is the tail of the existing CHANGELOG.md. Please use this as a guide on format and style.\n\n===\n\n" + "".join(
             last_lines)},
        {"role": "user",
         "content": f"The new version is {current_version} it is releasing on today's date: {datetime.now().date().isoformat()} (date format is ISO 8601 - YYYY-MM-DD)"},
        {"role": "user",
         "content": f"I will now give you commit summaries for the commits between {previous_version} and {current_version} from oldest to newest:" + "\n\n---\n\n".join(
             summaries)},
        {"role": "user",
         "content": f"Please give me the new changelog entry for version the new version {current_version}, given these commit messages, following the format of my current CHANGELOG.md. Give only the new entry, nothing else. Please put the most significant changes first."}
    ]

    print(f"Summarized commits, generating changelog entry using {model}.")
    completion = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0.4
    )
    new_changelog_entry = completion.choices[0].message['content']

    print(f"\nNew Changelog Entry:\n{new_changelog_entry}")

    # append new changelog entry to the file if --append is specified
    if append:
        with open(changelog_file, 'a') as file:
            # Ensure there's a double linebreak before the new content
            file.write('\n\n' + new_changelog_entry)
        print(f"New changelog entry has been appended to {changelog_file}.")


def entrypoint():
    parser = argparse.ArgumentParser(description="Automatically generate a changelog entry from git commits.")
    parser.add_argument('--version', '-v', type=str, default="HEAD", help="Current version of the software.")
    parser.add_argument('--changelog', '-c', type=str, default="CHANGELOG.md", help="Path to the CHANGELOG.md file.")
    parser.add_argument('-4', '--gpt4', '--gpt-4', action='store_true',
                        help="Use GPT-4 model if specified, otherwise use GPT-3.5 Turbo.")
    parser.add_argument('--append', '-a', action='store_true',
                        help="Automatically append the new changelog to the original file.")
    args = parser.parse_args()

    if '--help' in sys.argv or '-h' in sys.argv:
        parser.print_help()
    else:
        model = "gpt-4" if args.gpt4 else "gpt-3.5-turbo"
        main(args.version, args.changelog, model, args.append)


if __name__ == "__main__":
    entrypoint()
