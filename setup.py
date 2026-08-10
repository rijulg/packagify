import os
import setuptools

with open("README.md", "r") as readme:
    long_description = readme.read()

setuptools.setup(
    name="packagify",
    packages=["packagify"],
    version=os.environ["RELEASE_VERSION"],
    license="MIT",
    description="A packaging utility to treat folders as packages",
    author="Rijul Gupta",
    author_email="rijulg@gmail.com",
    url="https://github.com/rijulg/packagify",
    keywords=["Packaging", "Helper"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Utilities",
    ],
)
