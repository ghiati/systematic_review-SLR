from setuptools import setup, find_packages

setup(
    name="systematic_review",  # Fixed typo: was "systematic_revew"
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "streamlit",
        "pandas",
        "openpyxl",  # for Excel export
        "groq",
        "langchain"

    ],
    author="Mustapha GHIATI",
    author_email="Mustapha GHIATI",
    description="A systematic review analysis tool",
    long_description="A comprehensive tool for analyzing research articles with duplicate detection and AI screening capabilities.",
)