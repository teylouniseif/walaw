from setuptools import setup, find_packages

setup(
    name="erdos",
    version="0.1.0",
    author="",
    author_email="",
    description="",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/teylouniseif/walaw",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "fastapi",
        "uvicorn",
        "vocode",
    ],
)