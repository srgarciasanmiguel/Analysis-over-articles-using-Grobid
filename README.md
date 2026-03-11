# Analysis-over-articles-using-Grobid

[![DOI](https://zenodo.org/badge/1172867391.svg)](https://doi.org/10.5281/zenodo.18931883)

[![Tests](https://github.com/srgarciasanmiguel/Analisis-over-articles-using-Grobid/actions/workflows/tests.yml/badge.svg)](https://github.com/srgarciasanmiguel/Analisis-over-articles-using-Grobid/actions/workflows/tests.yml)

[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC_BY--SA_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

## Index

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Data](#data)
4. [Pipeline](#pipeline)
5. [Installation](#installation)
6. [Usage](#usage)
7. [Output](#output)
8. [Validation](#validation)
9. [License](#license)

## Overview

This project is a tool meant to analize academic papers, in PDF format, using Grobid, extracting information of each paper and generating a visual representation of the data.

It extracts the abstract of each paper to create a keyword cloud, counts the figures of each paper and extracts the links present in the papers.

## Prerequisites

- Docker
- Python 3.10 or newer
- Conda (optional)

### Compatibility

| Component | Version |
|-----------|---------|
| Python    | 3.10 – 3.12 (developed on 3.12.3) |
| Grobid    | 0.8.2-crf (default) |

> ⚠️ Python 3.9 and below are **not supported**.

The default Grobid image (`grobid:0.8.2-crf`) is the lightweight CRF-only variant, chosen for faster processing during testing. Heavier full-ML images can be swapped in for improved extraction reliability — browse available tags on [Docker Hub](https://hub.docker.com/r/grobid/grobid/tags).

## Data

13 open-access papers were downloaded from:

- doaj.org
    - Review of Current Simple Ultrasound Hardware Considerations, Designs, and Processing Opportunities
    - What is the “Source” of Open Source Hardware?
    - MAINSTREAMING METADATA INTO RESEARCH WORKFLOWS TO ADVANCE REPRODUCIBILITY AND OPEN GEOGRAPHIC INFORMATION SCIENCE
- arXiv.org
    - Percentile-Focused Regression Method for Applied Data with Irregular Error Structures
    - Predicting Gaia astrometry’s ability to constrain the populations of circumbinary planets
    - Floating-point–consistent cross-verification methodology for reproducible and interoperable DDA solvers with fair benchmarking
    - Language Model Goal Selection Differs from Humans’ in an Open-Ended Task
    - Ethical and Explainable AI in Reusable MLOps Pipelines
    - Solving adversarial examples requires solving exponential misalignment
    - Internet malware propagation: Dynamics and control through SEIRV epidemic model with relapse and intervention
    - Non-reciprocity and exchange-spring delay of domain-wall Walker breakdown in magnetic nanowires with azimuthal magnetization
    - Joint Hardware-Workload Co-Optimization for In-Memory Computing Accelerators
    - A Multi-Dimensional Quality Scoring Framework for Decentralized LLM Inference with Proof of Quality

## Pipeline

1. Convert PDFs → TEI XML using Grobid
2. Extract abstracts
3. Count figures per paper
4. Extract URLs
5. Generate keyword cloud
6. Create a visualization showing the number of figures per article
7. Create a list of the links found in each paper

## Installation

Install the repository:
```
git clone https://github.com/srgarciasanmiguel/Analysis-over-articles-using-Grobid.git
```

## Usage

Go to the project directory:
```
cd Analysis-over-articles-using-Grobid
```

Copy the PDF files of the papers to analize in the `/data` folder

> ⚠️ There are already 13 papers there, the ones listed in [data](#data), that were used for developing and testing the system. Remove them before using.

### Local Setup

Environment setup (optional):
```
conda env create -f environment.yml

conda activate grobid-analysis
```
> Creates the same environment that it was used to develop this system.

Run Grobid:
```
docker run --rm -p 8070:8070 grobid/grobid:0.8.2-crf
```
> In order to use other version of Grobid run that version instead.

Run script
```
python3 script/grobid_analisis.py
```

### Docker Setup

> To use other version of grobid change line 4 in `docker-compose.yml`.

To build it, and run it, for the first time, or if changes have been made:
```
docker compose up --build
```

To run it:
```
docker compose run --rm grobid_analysis
```
> Using this command leaves grobid running so remember to stop/kill it when it is no longer needed.

## Output

The program generates three files in the folder `/results` that will be created if it has not been yet:

1. figures_per_article.png
2. links_report.txt
3. wordcloud.png

![wordcloud_example](image.png)

![figures_per_article_example](image-1.png)

## Validation

The results have been validated manually for over 20 papers.

The keyword cloud generates correctly as long as the paper specifies which part is the abstract.

The figures sometimes detects a table as a figure and counts it as so.

The links as long as the link directs to a website and is clickable in the PDF is counted correctly. If it is a link to a part of the document it is not counted.

> Tested on 20+ papers — edge cases may exist beyond those documented above.

## License

This work is licensed under a [Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/).
