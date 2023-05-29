import argparse
import concurrent.futures
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import backoff
import openai
from git import Repo, InvalidGitRepositoryError
from tqdm import tqdm


# initialize openai api
openai.api_key = os.getenv("OPENAI_API_KEY")

script_dir = os.path.dirname(os.path.abspath(__file__))


# Cache the output
def load_messages(filename):
    with open(filename, 'r') as file:
        messages = json.load(file)
    return messages


message_text = load_messages(os.path.join(script_dir, "messages.json"))


def summarize(text, model="gpt-3.5-turbo"):
    system_message = open(os.path.join(script_dir, "./system/commit_summarizer.txt"), "r").read()

    # TODO use tiktoken to limit to 2048 tokens
    # Split text into lines and only take the first 50
    text = "\n".join(text.split("\n")[:100])

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": message_text["commit_summarizer"]["summarize_commit_details"].format(text)}
    ]

    completion = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0.25
    )
    return completion.choices[0].message['content']


def main(current_version="HEAD", changelog_file="CHANGELOG.md", model="gpt-4", append=False):
    if current_version is None or changelog_file is None:
        print("Error: Missing required arguments: 'current_version' and 'changelog_file'")
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

    # define the backoff strategy - 5, 10, 20 seconds
    backoff_strategy = backoff.on_exception(backoff.expo, (Exception,), max_tries=3, base=2, factor=5)

    @backoff_strategy
    def process_commit(commit):
        diff = repo.git.diff(commit.parents[0].hexsha, commit.hexsha)
        text = commit.message + "\n" + diff
        summary = summarize(text, model="gpt-3.5-turbo")
        timestamp = commit.committed_datetime.isoformat()  # ISO 8601 format
        formatted_commit_info = f"Commit: {commit.hexsha[:6]}\nTimestamp: {timestamp}\nMessage: {commit.message}\nSummary: {summary}"
        return formatted_commit_info

    # loop over all commits and get summaries in parallel
    summaries = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_commit, commit) for commit in commits}
        for future in tqdm(concurrent.futures.as_completed(futures), desc="Summarizing commits", total=len(commits)):
            try:
                summaries.append(future.result())
            except Exception as e:
                print(f"An error occurred: {e}")

    # read the tail of the current changelog file
    with open(changelog_file, 'r') as file:
        last_lines = file.readlines()[-40:]

    # generate a new changelog entry using OpenAI
    system_message = open(os.path.join(script_dir, "./system/changelog_writer.txt"), "r").read()
    messages = [
        {"role": "system", "content": system_message},
        {
            "role": "user",
            "content": message_text["changelog_writer"]["tail_changelog_user"].format("".join(last_lines))
        },
    ]

    if current_version == "HEAD":
        messages.append({
            "role": "user",
            "content": message_text["changelog_writer"]["unknown_version_user"]
        })
    else:
        messages.append({
            "role": "user",
            "content": message_text["changelog_writer"]["known_version_user"].format(current_version)
        })

    messages.append({
        "role": "user",
        "content": message_text["changelog_writer"]["releasing_date_user"].format(datetime.now().date().isoformat())
    })

    messages.extend([
        {
            "role": "user",
            "content": message_text["changelog_writer"]["commit_summaries_user"].format(
                previous_version,
                current_version,
                "\n\n---\n\n".join(summaries)
            )
        },
        {
            "role": "user",
            "content": message_text["changelog_writer"]["new_changelog_entry_user"].format(current_version)
        },
    ])

    print(f"Summarized commits, generating changelog entry using {model}.")
    completion = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0.1
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
    parser.add_argument('-3', '--gpt3', '--gpt-3', action='store_true',
                        help="Use GPT-3.5 Turbo model if specified, otherwise use GPT-4.")
    parser.add_argument('--append', '-a', action='store_true',
                        help="Automatically append the new changelog to the original file.")
    args = parser.parse_args()

    if '--help' in sys.argv or '-h' in sys.argv:
        parser.print_help()
    else:
        model = "gpt-3.5-turbo" if args.gpt3 else "gpt-4"
        main(args.version, args.changelog, model, args.append)


if __name__ == "__main__":
    entrypoint()
