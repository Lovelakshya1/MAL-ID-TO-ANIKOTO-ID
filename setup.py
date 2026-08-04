from setuptools import setup, find_packages

setup(
    name="anikoto-resolver",
    version="1.0.0",
    description="Resilient, high-performance anime MAL ID and Title resolver for Anikoto.cz",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Himmy Development Team",
    url="https://github.com/your-username/anikoto-resolver",
    packages=find_packages(),
    py_modules=["anikoto_resolver"],
    install_requires=[
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
        "lxml>=4.9.0",
    ],
    entry_points={
        "console_scripts": [
            "anikoto-resolver=anikoto_resolver.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
)
