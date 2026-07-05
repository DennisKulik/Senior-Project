# User Guide

## Authors 
Dennis Kulk & Corey Rogers
## Introduction

This project was developed as part of a Cal Poly senior project in support of Naval Innovations, an Instructionally Related Activity (IRA) focused on the development of an autonomous submarine.

The goal of this project is to provide a centralized pipeline for processing and visualizing submarine telemetry data. As testing data grows, manually organizing files and generating visualizations can become increasingly time consuming. This system automates that workflow and displays results through Grafana dashboards.

---

## Current Project Status

At the time of writing, the autonomous submarine has not yet been fully deployed. Because of this, the datasets used by the system are synthetic and were generated based on expected sensor outputs and operating conditions.

These datasets were created to allow development and testing of the data pipeline, cloud infrastructure, and dashboard visualizations before real telemetry becomes available.

As hardware development and testing continue, the system will likely require updates to accommodate real-world sensor behavior and additional telemetry sources.

---

## Project Background

The goal of Naval Innovations is to develop an autonomous submarine capable of operating without direct human control.

Once operational, the submarine is expected to generate telemetry from systems such as:

* IMUs
* Depth sensors
* Sonar systems
* Battery management systems
* Motor controllers

Managing and analyzing this information manually would become increasingly difficult and time consuming as testing progresses. This project was created to automate that process and provide a single location for viewing and analyzing telemetry data across tests.

---

## System Overview

The general workflow is:

1. Data is added or updated in the GitHub repository.
2. AWS webhook detects the update and starts the processing pipeline.
3. The data is processed and transformed into datasets suitable for analysis (Athena).
4. Grafana dashboards display the processed results.

This workflow is designed to minimize manual processing and provide a consistent view of project data.

---

## Viewing Data

Processed data can be viewed through the project's Grafana dashboards.

The dashboards are intended to help team members:

* Monitor sensor outputs
* Review testing results
* Analyze expected vehicle performance
* Identify trends and anomalies in collected data

Dashboard updates may take several minutes to appear after new data is submitted.

---

## Updating Data

To add new data to the system:

1. Upload or modify the appropriate files in the GitHub repository.
2. Commit and push the changes.
3. Wait for the processing pipeline to complete.

Once processing has finished, the updated information will be available through Grafana.

---

## Troubleshooting

### Dashboard Not Updating

Check that:

* Changes were successfully pushed to GitHub.
* The processing pipeline completed successfully.
* The dashboard has had time to refresh.

### Missing Data

Check that:

* The uploaded files are valid.
* Data follows the expected schema, or the SQL queries have been updated to accommodate schema changes.
* Required data files are present.
* Processing completed without errors.

If problems persist, review the AWS logs associated with the processing pipeline.
