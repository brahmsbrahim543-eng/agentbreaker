from setuptools import setup, find_packages

setup(
    name="agentbreaker",
    version="0.1.0",
    description="Detect and kill runaway AI agents in real-time",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="AgentBreaker",
    url="https://agentbreaker.dev",
    packages=find_packages(),
    install_requires=["httpx>=0.25.0"],
    extras_require={
        "langchain": ["langchain-core>=0.1.0"],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="ai agent monitoring safety guardrails langchain",
    project_urls={
        "Documentation": "https://docs.agentbreaker.dev",
        "Source": "https://github.com/agentbreaker/agentbreaker-python",
        "Bug Tracker": "https://github.com/agentbreaker/agentbreaker-python/issues",
    },
)
