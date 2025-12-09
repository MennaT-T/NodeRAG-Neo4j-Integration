from setuptools import setup, find_packages

setup(
    name="NodeRAG",
    version="0.1.0-custom",
    description="NodeRAG Neo4j Integration - Custom Version",
    packages=find_packages(),
    install_requires=[
        "neo4j==6.0.3",
        "google-generativeai==0.2.2",
        "google-genai==1.52.0",
        "openai==1.66.3",
        "networkx==3.4.2",
        "hnswlib_noderag==0.8.2",
        "pandas==2.2.3",
        "numpy==1.26.4",
        "pyarrow==19.0.1",
        "psutil==7.1.3",
        "PyPDF2==3.0.1",
        "rich==13.9.4",
        "tqdm==4.67.1",
        "PyYAML==6.0.2",
        "requests==2.32.3",
    ],
    python_requires='>=3.11',
    author="Custom NodeRAG Team",
    package_data={
        'NodeRAG': [
            'Vis/html/**/*',
            'utils/prompt/**/*',
        ],
    },
    include_package_data=True,
)

