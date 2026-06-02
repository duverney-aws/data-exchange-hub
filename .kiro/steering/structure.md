# Project Structure

## Repository Organization

This repository contains architecture documentation, presentations, and design specifications for the Pharma Data Exchange Hub platform.

## File Categories

### Architecture Documentation
- `Merck_CMO_3_Pattern_Architecture.md` - Complete slide deck with 3-pattern simplified architecture (v2.0)
- `CMO_Self_Service_Onboarding_Architecture.md` - Self-service portal and data contract architecture
- `AWS_Reference_Architecture.md` - Detailed AWS service architecture diagram
- `Merck-data-exchange-platform.md` - Original business requirements and problem statement
- `Merck_CMO_Platform_Agnostic.md` - Platform-agnostic design considerations

### Data Contracts & Schema
- `data-contract.yml` - Example data contract template (YAML format)
- `Data_Contract_Explained.md` - Comprehensive explanation of data contracts with JSON examples
- `Schema_Registry_Explained.md` - AWS Glue Schema Registry usage and patterns

### Presentations
- `cmo-onboarding-presentation.html` - CMO-facing onboarding presentation
- `enterprise-architect-presentation.html` - Technical architecture presentation
- `Merck_CMO_Enterprise_Architect_Presentation.md` - Enterprise architect slide deck
- `presentation.html` - General platform presentation
- `Merck Data Exchange Hub.pptx` - PowerPoint presentation
- `Pharma_Data_Exchange_Hub_Presentation.pptx` - Pharma-specific presentation

### Architecture Diagrams
- `architecture-diagram-code.py` - Python code to generate architecture diagrams using `diagrams` library
- `architecture.png` - Generated architecture diagram image
- `architecture-diagram-ascii.txt` - ASCII art architecture diagram
- `architecture_diagram.html` - HTML architecture visualization
- `pharma-architecture-simple.py` - Simplified architecture diagram code
- `pharma-aws-architecture.html` - AWS-specific architecture HTML

### Strategy Documents
- `Merck CMO Data Exchange power point.md` - PowerPoint outline
- `Merck CMO One Pager.md` - Executive summary (1 page)
- `Merck CMO Two pager.md` - Extended executive summary (2 pages)
- `Merck Data Exchange Strategy CMO.md` - Strategic overview
- `Executive Summary Presentation.md` - Executive presentation outline
- `PowerPoint_Presentation_Outline.md` - Presentation structure guide

### Technical Specifications
- `Connectivity_Requirements.md` - Network and connectivity requirements
- `platform-agnostics.md` - Platform-agnostic design principles
- `Merck CMO Structured-unstructured presentation.md` - Structured vs unstructured data handling
- `Merck COM Unstructured data.md` - Unstructured data processing details

### Project Management
- `MEMORY.md` - Project context and decisions log
- `prompt.txt` - Generation prompts and instructions

## Key Concepts

### Three Integration Patterns

1. **Pattern 1: Native Connectors** - Direct integration with modern platforms (Snowflake, Oracle, SQL Server, SAP, Databricks)
2. **Pattern 2: Secure Transfer** - Universal SFTP for any system (100% CMO coverage)
3. **Pattern 3: Unstructured AI** - AI-powered processing of PDFs, images, and IoT data

### Medallion Architecture

- **Bronze Layer** - Raw ingested data (immutable, partitioned, compressed)
- **Silver Layer** - Validated and cleansed data (schema validated, quality checked)
- **Gold Layer** - Business-ready aggregated data (optimized, conformed)

### Data Contract Components

- **Schema** - Field definitions, types, constraints (stored in Glue Schema Registry)
- **Quality Rules** - Validation logic (completeness, accuracy, uniqueness)
- **SLAs** - Service level agreements (timeliness, availability)
- **Delivery** - Frequency, schedule, format
- **Governance** - Access control, retention, compliance

## Documentation Conventions

- **Markdown** - Primary documentation format for architecture and technical specs
- **YAML** - Data contract definitions
- **Python** - Architecture diagram generation (using `diagrams` library)
- **HTML** - Presentation formats for stakeholder review
- **ASCII Art** - Text-based architecture diagrams for quick reference

## Naming Conventions

- CMO identifiers: `cmo-{name}` (e.g., `cmo-alpha`)
- Contract IDs: `CMO-{NAME}-{DOMAIN}-{NUMBER}` (e.g., `CMO-ALPHA-BATCH-001`)
- Schema names: `{cmo-id}-{data-type}` (e.g., `cmo-alpha-batch-records`)
- S3 paths: `s3://bucket/{layer}/{cmo-id}/{data-domain}/` (e.g., `s3://data-lake/bronze/cmo-alpha/batch-records/`)

## Version History

- **v1.0** - Initial 5-pattern architecture (included Data Exchange and Clean Rooms)
- **v2.0** - Simplified 3-pattern architecture (removed retiring services, focused on proven AWS services)
