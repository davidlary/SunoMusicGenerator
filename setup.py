"""
Setup script for SunoMusicGenerator.

Allows installation of the package and registers CLI commands.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="suno-music-generator",
    version="1.0.0",
    description="Transform scientific text into educational songs using Gemini and Suno APIs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="David Lary",
    author_email="david.lary@gmail.com",
    url="https://github.com/davidlary/SunoMusicGenerator",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "google-genai>=1.0.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "playwright>=1.40.0",
        "click>=8.0.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
            "pytest-asyncio>=0.21.0",
        ],
        "web": [
            "fastapi>=0.100.0",
            "uvicorn[standard]>=0.20.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "suno-music=src.cli.main:cli",
            "smg=src.cli.main:cli",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
