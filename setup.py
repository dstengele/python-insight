import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="jira_insight",
    version="0.6.0",
    author="Dennis Stengele",
    author_email="dennis@stengele.me",
    description="API client for the Insight app for Jira",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/schuppentier/python-insight",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=["lazy", "requests"],
)
