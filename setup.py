from setuptools import setup, find_packages

with open("README.md", "r") as readme_file:
    readme = readme_file.read()

requirements = ["gitpython>=3.1.14", "tqdm>=4.60.0", "openai>=0.27.0", "backoff>=1.10.0", "tiktoken>=0.4.0", "termcolor>=2.3.0"]

setup(
    name="logedit",
    version="0.1.1",
    author="Greg Priday",
    author_email="greg@siteorigin.com",
    description="A package to auto-generate changelogs from git commits using OpenAI's APIs",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/gregpriday/logedit/",
    packages=find_packages(),
    install_requires=requirements,
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: MIT License",
    ],
    entry_points={
        "console_scripts": [
            "logedit=logedit.logedit:entrypoint",
        ],
    },
)
