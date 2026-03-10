# Analisis-over-articles-using-Grobid

[![DOI](https://zenodo.org/badge/1172867391.svg)](https://doi.org/10.5281/zenodo.18931883)

## Index

1. [Overview](#overview)
2. [Data](#data)
3. [Pipeline](#pipeline)
4. [Installation](#installation)
5. [Validation](#validation)

## Overview

This project analyzes research papers using Grobid to extract structured information from PDFs.

Developed on python 3.12.3

Working versions:

- 3.12
- 3.11
- 3.10
- It does not work on 3.9

The pipeline performs:

- Abstract extraction
- Keyword cloud generation
- Figure counting
- Link extraction

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

### Environment Setup
```
conda env create -f environment.yml

conda activate grobid-analysis
```

### Run Grobid

docker run --rm -p 8070:8070 8070:8070 grobid/grobid:0.8.2-crf

    - This is the version I have used because it is lighter, so it is faster for tests. The program should work with other versions of grobid without any issues.

### Run Scripts

python3 script/grobid_analisis.py

## Docker Installation

To use other version of grobid change line 4 in docker compose.

To build it, and run it, for the first time, or if changes have been made:
```
docker compose up --build
```

To run it:
```
docker compose run --rm grobid_analysis
```

## Validation

wip