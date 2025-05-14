
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="chess-game-review",  
    version="0.1.0",              
    author="Ganeshdarshan Bhat",
    author_email="bhatganeshdarshan10@gmail.com",
    description="A Flask server for chess game analysis and game review using Stockfish.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bhatganeshdarshan/chess-game-review", 
    packages=find_packages(where=".", include=['chess_analyzer', 'chess_analyzer.*']), 
    # Or explicitly: packages=['chess_analyzer'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License", 
        "Operating System :: OS Independent",
        "Framework :: Flask",
        "Topic :: Games/Entertainment :: Board Games",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires='>=3.7',  
    install_requires=[
        "Flask>=2.0",
        "python-chess>=1.9", 
        "Flask-CORS>=3.0",   
    ],
    entry_points={
        'console_scripts': [
            'chess-analyzer-server=chess_analyzer.server:main_cli',
        ],
    },
)