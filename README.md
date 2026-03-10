# Analisis-over-articles-using-Grobid

## Overview

This project analyzes open-access research papers using Grobid to extract structured information from PDFs.

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
3. Generate keyword cloud
4. Count figures per paper
5. Extract URLs

## Installation

### Environment Setup

conda env create -f environment.yml
conda activate grobid-analysis

### Run Grobid

docker run --rm -p 8070:8070 8070:8070 grobid/grobid:0.8.2-crf

### Run Scripts

python3 script/grobid_analisis.py

## Docker Installation

docker compose up --build
docker compose run --rm grobid_analysis