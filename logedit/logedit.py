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
import tiktoken
from termcolor import colored


# initialize openai api
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("Please set the OPENAI_API_KEY environment variable. See: "
                     "https://github.com/openai/openai-python#usage")

script_dir = os.path.dirname(os.path.abspath(__file__))


# Cache the output
def load_messages(filename):
    with open(filename, 'r') as file:
        messages = json.load(file)
    return messages


message_text = load_messages(os.path.join(script_dir, "messages.json"))


def summarize(text, model="gpt-3.5-turbo"):
    # Get encoding for gpt-3.5-turbo
    encoding = tiktoken.encoding_for_model(model)

    # Limit the text to 2048 tokens.
    # GPT-3.5 has a limit of 4096 tokens, but we need to leave room for the system message and response.
    text = encoding.decode(encoding.encode(text)[:2048])

    with open(os.path.join(script_dir, "./system/commit_summarizer.txt"), "r") as file:
        system_message = file.read()

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
        print(colored("Error: Missing required arguments: 'current_version' and 'changelog_file'", 'red'))
        return

    try:
        repo = Repo(os.getcwd())
    except InvalidGitRepositoryError:
        print(colored(f"The current directory ({os.getcwd()}) is not a valid Git repository. Please navigate to a Git repository and try again.", 'red'))
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

    print(colored(f"Previous version is: {previous_version}", 'yellow'))
    print(colored(f"Current version is: {current_version}", 'yellow'))

    # get commits between recent version and current version
    commits = list(repo.iter_commits(f'{previous_version}..HEAD'))

    print(colored(f"Total commits: {len(commits)}", 'cyan'))

    # define the backoff strategy - 5, 10, 20 seconds
    backoff_strategy = backoff.on_exception(backoff.expo, (Exception,), max_tries=3, base=2, factor=5)

    @backoff_strategy
    def process_commit(diff, commit):
        text = commit.message + "\n" + diff
        summary = summarize(text, model="gpt-3.5-turbo")
        timestamp = commit.committed_datetime.isoformat()  # ISO 8601 format
        formatted_commit_info = f"Commit: {commit.hexsha[:6]}\nTimestamp: {timestamp}\nMessage: {commit.message}\nSummary: {summary}"
        return formatted_commit_info

    # get all commit diffs in a single thread
    commit_diffs = []
    for commit in commits:
        diff = repo.git.diff(commit.parents[0].hexsha, commit.hexsha)
        commit_diffs.append((diff, commit))

    # loop over all commits and get summaries in parallel
    summaries = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_commit, diff, commit) for diff, commit in commit_diffs}
        for future in tqdm(concurrent.futures.as_completed(futures), desc="Summarizing commits", total=len(commits)):
            try:
                summaries.append(future.result())
            except Exception as e:
                print(colored(f"An error occurred: {e}", 'red'))

    # read the tail of the current changelog file
    with open(changelog_file, 'r') as file:
        last_lines = file.readlines()[-40:]

    with open(os.path.join(script_dir, "./system/changelog_writer.txt"), "r") as file:
        system_message = file.read()

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

    # generate a new changelog entry using OpenAI's API
    print(colored(f"Summarized commits, generating changelog entry using {model}.", 'green'))
    completion = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0.1
    )
    new_changelog_entry = completion.choices[0].message['content']

    print(colored(f"\nNew Changelog Entry:\n", 'blue'))
    print(new_changelog_entry)

    # append new changelog entry to the file if --append is specified
    if append:
        with open(changelog_file, 'a') as file:
            # Ensure there's a double linebreak before the new content
            file.write('\n\n' + new_changelog_entry)
        print(colored(f"New changelog entry has been appended to {changelog_file}.", 'magenta'))


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

        # If we want to use GPT-4, we need to check that it's available for this user, otherwise show a warning
        if model == "gpt-4":
            try:
                openai.Model.retrieve(model)
            except Exception as e:
                print(colored(f"GPT-4 model is not available for this user. It is recommended. Please check your access permissions. Defaulting to GPT-3.5 Turbo. Error: {e}",'yellow'))
                model = "gpt-3.5-turbo"

        main(args.version, args.changelog, model, args.append)


if __name__ == "__main__":
    entrypoint()