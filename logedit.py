import os
import openai
from git import Repo
from tqdm import tqdm
import argparse
from datetime import datetime

# load openai API key
from dotenv import load_dotenv
load_dotenv()

# initialize openai api
openai.api_key = os.getenv("OPENAI_API_KEY")

script_dir = os.path.dirname(os.path.abspath(__file__))

# define a function to send text to OpenAI API and get summary
def summarize(text):
    system_message = open(os.path.join(script_dir, "./system/commit_summarizer.txt"), "r").read()
    completion = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Summarize the following commit details:\n\n{text}"}
      ]
    )
    return completion.choices[0].message['content']


def main(current_version, changelog_file):
    # initialize git repo
    repo = Repo(os.getcwd())

    # get all tags in repo
    tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)

    # find the most recent version
    recent_version = tags[-1]

    print(f"Most recent version is: {recent_version}")

    # get commits between recent version and current version
    commits = list(repo.iter_commits(f'{recent_version}..HEAD'))

    print(f"Total commits: {len(commits)}")

    # loop over all commits and get summaries
    summaries = []
    for commit in tqdm(commits, desc="Summarizing commits"):
        diff = repo.git.diff(commit.parents[0].hexsha, commit.hexsha)
        text = commit.message + "\n" + diff
        summary = summarize(text)
        summaries.append(summary)

    # read the tail of the current changelog file
    with open(changelog_file, 'r') as file:
        last_lines = file.readlines()[-40:]

    # generate a new changelog entry using OpenAI
    system_message = open(os.path.join(script_dir, "./system/changelog_writer.txt"), "r").read()
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": "Here is the tail of my existing CHANGELOG.md. Please use this as a guide on format and style.\n\n===\n\n" + "".join(last_lines)},
        {"role": "user", "content": f"The new version is {current_version} and today's date is {datetime.now().date().isoformat()} (date format is ISO 8601 - YYYY-MM-DD)"},
        {"role": "user", "content": f"I will now give you commit summaries for the commits between {recent_version} and {current_version} from oldest to newest:" + "\n\n---\n\n".join(summaries)},
        {"role": "user", "content": "Please give me the new changelog entry for version the new version {current_version}, given these commit messages, following the format of my current CHANGELOG.md. Give only the new entry, nothing else. Please put the most significant changes first."}
    ]

    print("Summarized commits, generating changelog entry...")
    completion = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )
    new_changelog_entry = completion.choices[0].message['content']

    print(f"\nNew Changelog Entry:\n{new_changelog_entry}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automatically generate a changelog entry from git commits.")
    parser.add_argument('current_version', type=str, default="HEAD", nargs="?", help="Current version of the software.")
    parser.add_argument('changelog_file', type=str, default="CHANGELOG.md", nargs="?", help="Path to the CHANGELOG.md file.")
    args = parser.parse_args()

    main(args.current_version, args.changelog_file)
