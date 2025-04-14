import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cachecade",
    version="0.1.0",
    author="Your Name",
    author_email="paul@picazo.com",
    description="A flexible caching decorator for Flask that supports Replit, Redis, and in-memory storage.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ppicazo/cachecade",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "Flask>=1.0",
        "replit>=0.0.1",
    ],
    extras_require={
        "redis": ["redis>=3.5.3"],
    },
)
