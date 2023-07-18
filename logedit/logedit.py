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


def count_tokens(text, model):
    tokens = tiktoken.encoding_for_model(model).encode(text)
    return len(tokens)


# initialize openai api
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    print("OPENAI_API_KEY environment variable not found. Please enter it below:")
    openai.api_key = input()
    if not openai.api_key:
        raise ValueError("No API Key provided. Terminating.")

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


def get_version_tags(repo, current_version):
    if ':' in current_version:
        previous_version, current_version = current_version.split(':')
    else:
        # get all tags in repo
        tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)

        # Filter for only tags that follow the format of a version number (with optional v prefix)
        version_tags = [tag for tag in tags if re.match(r"^v?(\d+\.)*\d+$", str(tag))]

        # find the most recent version
        previous_version = version_tags[-1] if version_tags else None

    return previous_version, current_version


def get_commits(repo, previous_version):
    # get commits between recent version and current version
    commits = list(repo.iter_commits(f'{previous_version}..HEAD'))

    print(colored(f"Total commits: {len(commits)}", 'cyan'))

    return commits


def summarize_commits(commits, repo, model):
    backoff_strategy = backoff.on_exception(backoff.expo, (Exception,), max_tries=3, base=2, factor=5)

    @backoff_strategy
    def process_commit(diff, commit):
        text = commit.message + "\n" + diff
        summary = summarize(text, model=model)
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

    return summaries


def get_changelog_tail(changelog_file):
    with open(changelog_file, 'r') as file:
        last_lines = file.readlines()[-40:]

    return last_lines


def generate_new_changelog_entry(last_lines, summaries, previous_version, current_version, model):
    with open(os.path.join(script_dir, "./system/changelog_writer.txt"), "r") as file:
        system_message = file.read()

    def generate_single_changelog_entry(chunked_summaries):
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
                    "\n\n---\n\n".join(chunked_summaries)
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

        # Display the entry to the user in a different color
        print(colored(f"Generated changelog entry:\n{completion.choices[0].message['content']}", 'yellow'))

        return completion.choices[0].message['content']

    def chunk_summaries(summaries):
        chunks = []
        chunk = []
        tokens = 0
        for summary in summaries:
            tokens_summary = count_tokens(summary, model)
            if tokens + tokens_summary > 4096:
                chunks.append(chunk)
                chunk = []
                tokens = 0
            chunk.append(summary)
            tokens += tokens_summary
        if chunk:
            chunks.append(chunk)
        return chunks

    chunks = chunk_summaries(summaries)
    chunked_changelogs = [generate_single_changelog_entry(chunk) for chunk in chunks]

    # combine all the changelogs entries into a single changelog entry
    if len(chunked_changelogs) > 1:
        with open(os.path.join(script_dir, "./system/changelog_combiner.txt"), "r") as file:
            system_message = file.read()

        print(colored(f"Combining chunked commits using {model}.", 'green'))
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": message_text["changelog_writer"]["combine_changelogs"].format(
                "\n\n".join(chunked_changelogs))},
        ]
        completion = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=0.1
        )
        return completion.choices[0].message['content']

    return chunked_changelogs[0]


def append_changelog(new_changelog_entry, changelog_file, append):
    print(colored(f"\nNew Changelog Entry:\n", 'blue'))
    print(new_changelog_entry)

    # append new changelog entry to the file if --append is specified
    if append:
        with open(changelog_file, 'a') as file:
            # Ensure there's a double linebreak before the new content
            file.write('\n\n' + new_changelog_entry)
        print(colored(f"New changelog entry has been appended to {changelog_file}.", 'magenta'))


def main(current_version="HEAD", changelog_file="CHANGELOG.md", model="gpt-4", append=False, branches=None):
    if current_version is None or changelog_file is None:
        print(colored("Error: Missing required arguments: 'current_version' and 'changelog_file'", 'red'))
        return

    try:
        repo = Repo(os.getcwd())
    except InvalidGitRepositoryError:
        print(colored(
            f"The current directory ({os.getcwd()}) is not a valid Git repository. Please navigate to a Git repository and try again.",
            'red'))
        sys.exit(1)

    if branches:
        branch1, branch2 = branches.split(':')
        previous_version = branch1
        current_version = branch2
    else:
        previous_version, current_version = get_version_tags(repo, current_version)

    print(colored(f"Previous version is: {previous_version}", 'yellow'))
    print(colored(f"Current version is: {current_version}", 'yellow'))

    commits = get_commits(repo, previous_version)

    summaries = summarize_commits(commits, repo, model)

    last_lines = get_changelog_tail(changelog_file)

    new_changelog_entry = generate_new_changelog_entry(last_lines, summaries, previous_version, current_version, model)

    append_changelog(new_changelog_entry, changelog_file, append)


def entrypoint():
    parser = argparse.ArgumentParser(description="Automatically generate a changelog entry from git commits.")
    parser.add_argument('--version', '-v', type=str, default="HEAD", help="Current version of the software.")
    parser.add_argument('--changelog', '-c', type=str, default="CHANGELOG.md", help="Path to the CHANGELOG.md file.")
    parser.add_argument('-3', '--gpt3', '--gpt-3', action='store_true',
                        help="Use GPT-3.5 Turbo model if specified, otherwise use GPT-4.")
    parser.add_argument('--append', '-a', action='store_true',
                        help="Automatically append the new changelog to the original file.")
    parser.add_argument('--branches', '-b', type=str,
                        help="Optional argument to specify two branches. Input should be in the format 'branch1:branch2'. If not provided, the script will use version tags to determine the range of commits.")
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
                print(colored(
                    f"GPT-4 model is not available for this user. It is recommended. Please check your access permissions. Defaulting to GPT-3.5 Turbo. Error: {e}",
                    'yellow'))
                model = "gpt-3.5-turbo"

        main(args.version, args.changelog, model, args.append, args.branches)


if __name__ == "__main__":
    entrypoint()
