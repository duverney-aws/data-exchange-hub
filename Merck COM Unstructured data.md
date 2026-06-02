Great question! The current proposal **primarily focuses on structured data** (batch records, quality events, equipment data, etc.). However, we can absolutely extend the architecture to handle **unstructured data**, which is critical for pharma manufacturing.

Let me provide an updated view that incorporates unstructured data handling:

---

# Unstructured Data Considerations for Pharma Data Exchange Hub

## Common Unstructured Data Types from CMOs

| Data Type | Examples | Volume | Use Cases |
|-----------|----------|--------|-----------|
| **Documents** | Batch records (PDF), CoAs, SOPs, Deviation reports | Medium | Compliance, audit, quality review |
| **Images** | Visual inspection images, label scans, equipment photos | High | Quality control, defect detection |
| **Sensor/IoT Data** | Time-series logs, equipment telemetry (semi-structured) | Very High | Predictive maintenance, process optimization |
| **Audio/Video** | Manufacturing floor recordings, training videos | Medium | Compliance, investigations |
| **Emails/Communications** | CMO correspondence, change notifications | Low-Medium | Audit trail, issue tracking |
| **Lab Data** | Chromatography files, spectral data, raw instrument output | High | Quality analysis, release testing |

---

## Updated Architecture: Structured + Unstructured Data

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CMO DATA SOURCES                                   │
│                                                                              │
│   STRUCTURED                              UNSTRUCTURED                       │
│   ┌─────────────┐                        ┌─────────────┐                    │
│   │ MES/ERP     │                        │ Documents   │                    │
│   │ LIMS        │                        │ Images      │                    │
│   │ QMS         │                        │ IoT/Sensor  │                    │
│   │ Historian   │                        │ Lab Files   │                    │
│   └──────┬──────┘                        └──────┬──────┘                    │
└──────────┼──────────────────────────────────────┼────────────────────────────┘
           │                                      │
           ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                                      │
│                                                                              │
│   STRUCTURED PATTERNS                    UNSTRUCTURED PATTERNS              │
│   ┌─────────────┐                        ┌─────────────┐                    │
│   │ Pattern 1-4 │                        │ Pattern 5   │                    │
│   │ (As defined)│                        │ Document/   │                    │
│   │             │                        │ Media Ingest│                    │
│   └──────┬──────┘                        └──────┬──────┘                    │
│          │                                      │                            │
│          │    ┌─────────────────────────────────┤                            │
│          │    │                                 │                            │
│          ▼    ▼                                 ▼                            │
│   ┌─────────────────┐                   ┌─────────────────┐                 │
│   │ AWS Transfer    │                   │ AWS Transfer    │                 │
│   │ Family / Data   │                   │ Family          │                 │
│   │ Exchange        │                   │ (Large files)   │                 │
│   └────────┬────────┘                   └────────┬────────┘                 │
│            │                                     │                           │
│            │         ┌───────────────────────────┤                           │
│            │         │                           │                           │
│            ▼         ▼                           ▼                           │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      AMAZON S3 DATA LAKE                             │   │
│   │   ┌─────────────────────────┐    ┌─────────────────────────┐        │   │
│   │   │     STRUCTURED ZONE     │    │    UNSTRUCTURED ZONE    │        │   │
│   │   │   s3://merck-cmo-data/  │    │  s3://merck-cmo-data/   │        │   │
│   │   │   structured/           │    │  unstructured/          │        │   │
│   │   │   ├── bronze/           │    │  ├── documents/         │        │   │
│   │   │   ├── silver/           │    │  ├── images/            │        │   │
│   │   │   └── gold/             │    │  ├── iot-timeseries/    │        │   │
│   │   │                         │    │  ├── lab-data/          │        │   │
│   │   │                         │    │  └── media/             │        │   │
│   │   └─────────────────────────┘    └─────────────────────────┘        │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROCESSING LAYER                                     │
│                                                                              │
│   STRUCTURED PROCESSING              UNSTRUCTURED PROCESSING                │
│   ┌─────────────────────┐           ┌─────────────────────────────────────┐ │
│   │                     │           │                                     │ │
│   │  AWS Glue           │           │  ┌─────────────┐  ┌─────────────┐  │ │
│   │  (ETL + Quality)    │           │  │  Amazon     │  │  Amazon     │  │ │
│   │                     │           │  │  Textract   │  │  Rekognition│  │ │
│   │  Amazon Athena      │           │  │  (Doc OCR)  │  │  (Image AI) │  │ │
│   │  (SQL Analytics)    │           │  └─────────────┘  └─────────────┘  │ │
│   │                     │           │                                     │ │
│   │  Amazon Redshift    │           │  ┌─────────────┐  ┌─────────────┐  │ │
│   │  (Data Warehouse)   │           │  │  Amazon     │  │  Amazon     │  │ │
│   │                     │           │  │  Comprehend │  │  Transcribe │  │ │
│   └─────────────────────┘           │  │  (NLP)      │  │  (Audio)    │  │ │
│                                     │  └─────────────┘  └─────────────┘  │ │
│                                     │                                     │ │
│                                     │  ┌─────────────┐  ┌─────────────┐  │ │
│                                     │  │  Amazon     │  │  Amazon     │  │ │
│                                     │  │  Bedrock    │  │  OpenSearch │  │ │
│                                     │  │  (Gen AI)   │  │  (Search)   │  │ │
│                                     │  └─────────────┘  └─────────────┘  │ │
│                                     │                                     │ │
│                                     │  ┌─────────────────────────────┐   │ │
│                                     │  │  Amazon Timestream          │   │ │
│                                     │  │  (IoT Time-Series DB)       │   │ │
│                                     │  └─────────────────────────────┘   │ │
│                                     └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONSUMPTION LAYER                                    │
│                                                                              │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│   │  Unified Search │  │  Analytics &    │  │  AI/ML          │            │
│   │  (OpenSearch)   │  │  BI Dashboards  │  │  Applications   │            │
│   │                 │  │  (QuickSight)   │  │  (SageMaker)    │            │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘            │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    AMAZON BEDROCK - GEN AI LAYER                     │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│   │   │ Document    │  │ Quality     │  │ Knowledge   │                 │   │
│   │   │ Q&A         │  │ Insights    │  │ Assistant   │                 │   │
│   │   │ (RAG)       │  │ Generation  │  │ (Chatbot)   │                 │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                 │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pattern 5: Unstructured Data Ingestion

**New pattern specifically for documents, images, and media files:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PATTERN 5: UNSTRUCTURED DATA INGESTION                   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         CMO SOURCES                                  │   │
│   │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │   │
│   │   │  Batch  │  │  CoA    │  │ Visual  │  │  IoT    │  │  Lab    │  │   │
│   │   │ Records │  │  PDFs   │  │ Inspect │  │ Sensors │  │ Instrum │  │   │
│   │   │ (PDF)   │  │         │  │ Images  │  │         │  │  Files  │  │   │
│   │   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  │   │
│   └────────┼────────────┼────────────┼────────────┼────────────┼────────┘   │
│            │            │            │            │            │            │
│            └────────────┴────────────┼────────────┴────────────┘            │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    INGESTION OPTIONS                                 │   │
│   │                                                                      │   │
│   │   Option A              Option B              Option C               │   │
│   │   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐         │   │
│   │   │ AWS Transfer│      │ S3 Direct   │      │ AWS IoT     │         │   │
│   │   │ Family      │      │ Upload      │      │ Core        │         │   │
│   │   │ (SFTP)      │      │ (Pre-signed │      │ (Streaming) │         │   │
│   │   │             │      │  URLs)      │      │             │         │   │
│   │   │ Best for:   │      │ Best for:   │      │ Best for:   │         │   │
│   │   │ Large files │      │ Portal      │      │ Real-time   │         │   │
│   │   │ Batch upload│      │ integration │      │ sensor data │         │   │
│   │   └──────┬──────┘      └──────┬──────┘      └──────┬──────┘         │   │
│   └──────────┼─────────────────────┼─────────────────────┼───────────────┘   │
│              │                     │                     │                  │
│              └─────────────────────┼─────────────────────┘                  │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    S3 LANDING ZONE                                   │   │
│   │                    (Unstructured Bucket)                             │   │
│   │                                                                      │   │
│   │   s3://merck-cmo-unstructured/                                      │   │
│   │   ├── {cmo-id}/                                                     │   │
│   │   │   ├── documents/                                                │   │
│   │   │   ├── images/                                                   │   │
│   │   │   ├── iot-data/                                                 │   │
│   │   │   └── lab-files/                                                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    EVENT-DRIVEN PROCESSING                           │   │
│   │                    (S3 Event → EventBridge → Step Functions)         │   │
│   │                                                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │                  PROCESSING WORKFLOW                         │   │   │
│   │   │                                                              │   │   │
│   │   │   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │   │   │
│   │   │   │ Detect  │───▶│ Extract │───▶│ Enrich  │───▶│ Index   │ │   │   │
│   │   │   │ Type    │    │ Content │    │ Metadata│    │ & Store │ │   │   │
│   │   │   └─────────┘    └─────────┘    └─────────┘    └─────────┘ │   │   │
│   │   │       │              │              │              │       │   │   │
│   │   │       ▼              ▼              ▼              ▼       │   │   │
│   │   │   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐│   │   │
│   │   │   │ Lambda  │    │Textract │    │Comprehend│   │OpenSearch││   │   │
│   │   │   │ (MIME   │    │Rekognit.│    │ Bedrock │    │ Glue    ││   │   │
│   │   │   │  detect)│    │Transcribe│   │         │    │ Catalog ││   │   │
│   │   │   └─────────┘    └─────────┘    └─────────┘    └─────────┘│   │   │
│   │   └──────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Unstructured Data Processing Services

### Document Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DOCUMENT PROCESSING PIPELINE                             │
│                                                                              │
│   INPUT                    PROCESSING                      OUTPUT           │
│   ┌─────────┐             ┌─────────────────┐             ┌─────────────┐   │
│   │         │             │                 │             │             │   │
│   │  Batch  │            │  Amazon         │             │ Structured  │   │
│   │ Record  │───────────▶│  Textract       │────────────▶│ JSON with:  │   │
│   │  (PDF)  │             │                 │             │ • Tables    │   │
│   │         │             │  • OCR          │             │ • Forms     │   │
│   └─────────┘             │  • Table extract│             │ • Key-Value │   │
│                           │  • Form extract │             │             │   │
│   ┌─────────┐             └─────────────────┘             └──────┬──────┘   │
│   │         │                                                    │          │
│   │  CoA    │                     │                              │          │
│   │  (PDF)  │─────────────────────┘                              │          │
│   │         │                                                    │          │
│   └─────────┘                                                    ▼          │
│                                                          ┌─────────────┐   │
│                                                          │ Store in    │   │
│                                                          │ S3 (JSON) + │   │
│                                                          │ Index in    │   │
│                                                          │ OpenSearch  │   │
│                                                          └─────────────┘   │
│                                                                              │
│   USE CASES:                                                                │
│   • Extract batch parameters from scanned records                           │
│   • Parse Certificate of Analysis data                                      │
│   • Digitize legacy paper-based documentation                               │
│   • Enable full-text search across all CMO documents                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Image Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IMAGE ANALYSIS PIPELINE                                  │
│                                                                              │
│   INPUT                    PROCESSING                      OUTPUT           │
│   ┌─────────┐             ┌─────────────────┐             ┌─────────────┐   │
│   │ Visual  │             │                 │             │             │   │
│   │Inspection│───────────▶│  Amazon         │────────────▶│ • Defect    │   │
│   │ Images  │             │  Rekognition    │             │   detected  │   │
│   │         │             │                 │             │   (Y/N)     │   │
│   └─────────┘             │  • Custom Labels│             │ • Defect    │   │
│                           │    (trained on  │             │   type      │   │
│   ┌─────────┐             │    pharma       │             │ • Confidence│   │
│   │ Label   │             │    defects)     │             │   score     │   │
│   │ Scans   │─────────────│  • Object detect│             │ • Bounding  │   │
│   │         │             │  • Text in image│             │   box       │   │
│   └─────────┘             └─────────────────┘             └──────┬──────┘   │
│                                                                  │          │
│   ┌─────────┐                                                    │          │
│   │Equipment│                                                    │          │
│   │ Photos  │────────────────────────────────────────────────────┘          │
│   │         │                                                    │          │
│   └─────────┘                                                    ▼          │
│                                                          ┌─────────────┐   │
│                                                          │ Store       │   │
│                                                          │ metadata +  │   │
│                                                          │ trigger     │   │
│                                                          │ alerts      │   │
│                                                          └─────────────┘   │
│                                                                              │
│   USE CASES:                                                                │
│   • Automated visual inspection quality control                             │
│   • Label verification and compliance checking                              │
│   • Equipment condition monitoring                                          │
│   • Packaging integrity verification                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### IoT/Time-Series Data Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IOT / TIME-SERIES PIPELINE                               │
│                                                                              │
│   CMO FACILITY                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐              │   │
│   │   │  Temp   │  │Pressure │  │  Flow   │  │Vibration│              │   │
│   │   │ Sensors │  │ Sensors │  │ Meters  │  │ Sensors │              │   │
│   │   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘              │   │
│   │        │            │            │            │                    │   │
│   │        └────────────┴─────┬──────┴────────────┘                    │   │
│   │                           │                                        │   │
│   │                    ┌──────▼──────┐                                 │   │
│   │                    │  IoT        │                                 │   │
│   │                    │  Gateway    │                                 │   │
│   │                    └──────┬──────┘                                 │   │
│   └───────────────────────────┼─────────────────────────────────────────┘   │
│                               │                                             │
│                               │  MQTT / HTTPS                               │
│                               ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      AWS IOT CORE                                    │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  • Device authentication (X.509 certificates)               │   │   │
│   │   │  • Message routing rules                                    │   │   │
│   │   │  • Protocol translation                                     │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                          │
│              ┌───────────────────┼───────────────────┐                     │
│              │                   │                   │                     │
│              ▼                   ▼                   ▼                     │
│   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐             │
│   │ Amazon          │ │ Amazon          │ │ Amazon S3       │             │
│   │ Timestream      │ │ Kinesis Data    │ │ (Raw archive)   │             │
│   │ (Time-series DB)│ │ Firehose        │ │                 │             │
│   │                 │ │ (Streaming ETL) │ │                 │             │
│   └────────┬────────┘ └────────┬────────┘ └─────────────────┘             │
│            │                   │                                           │
│            └─────────┬─────────┘                                           │
│                      │                                                     │
│                      ▼                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    ANALYTICS & ALERTING                              │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│   │   │ Amazon      │  │ Amazon      │  │ AWS Lambda  │                 │   │
│   │   │ Managed     │  │ QuickSight  │  │ (Anomaly    │                 │   │
│   │   │ Grafana     │  │ (Dashboards)│  │  Alerts)    │                 │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                 │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   USE CASES:                                                                │
│   • Real-time process monitoring                                            │
│   • Environmental condition tracking (temp, humidity, pressure)             │
│   • Predictive maintenance based on equipment telemetry                     │
│   • Batch process parameter trending                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Generative AI Layer (Amazon Bedrock)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GENERATIVE AI CAPABILITIES                               │
│                    (Amazon Bedrock + Knowledge Bases)                       │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    KNOWLEDGE BASE (RAG)                              │   │
│   │                                                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  Data Sources (Indexed)                                      │   │   │
│   │   │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │   │   │
│   │   │  │  Batch  │  │  SOPs   │  │Deviation│  │  CoAs   │        │   │   │
│   │   │  │ Records │  │         │  │ Reports │  │         │        │   │   │
│   │   │  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                              │                                      │   │
│   │                              ▼                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  Vector Store (OpenSearch Serverless)                        │   │   │
│   │   │  • Document embeddings                                       │   │   │
│   │   │  • Semantic search capability                                │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    USE CASE EXAMPLES                                 │   │
│   │                                                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  1. DOCUMENT Q&A                                             │   │   │
│   │   │     User: "What was the yield for Batch ABC-123?"           │   │   │
│   │   │     System: Searches batch records → Returns answer          │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  2. DEVIATION ANALYSIS                                       │   │   │
│   │   │     User: "Summarize all temperature deviations at CMO X"   │   │   │
│   │   │     System: Aggregates deviation reports → Generates summary │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  3. QUALITY INSIGHTS                                         │   │   │
│   │   │     User: "Compare quality metrics across all CMOs"         │   │   │
│   │   │     System: Analyzes CoAs + batch data → Generates report    │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  4. KNOWLEDGE ASSISTANT                                      │   │   │
│   │   │     User: "What's the SOP for handling out-of-spec results?"│   │   │
│   │   │     System: Retrieves relevant SOPs → Provides guidance      │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   FOUNDATION MODELS AVAILABLE:                                              │
│   • Claude (Anthropic) - Document analysis, summarization                   │
│   • Titan (Amazon) - Embeddings, text generation                            │
│   • Llama (Meta) - General purpose                                          │
│   • Stable Diffusion - Image analysis/generation                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Updated Pattern Summary (Including Unstructured)

| Pattern | Data Type | Best For | Key Services | Time to Value |
|---------|-----------|----------|--------------|---------------|
| **1 - Data Exchange** | Structured | Cloud-native CMOs | Data Exchange, S3, Glue | 1-2 weeks |
| **2 - Clean Rooms** | Structured | Privacy-sensitive | Clean Rooms, S3 | 2-3 weeks |
| **3 - Snowflake** | Structured | Snowflake CMOs | S3, Glue, PrivateLink | 1-2 weeks |
| **4 - Transfer** | Structured + Unstructured | Legacy/on-prem | Transfer Family, S3 | 2-4 weeks |
| **5 - Unstructured** | Documents, Images, IoT | All CMOs | Textract, Rekognition, IoT Core, Bedrock | 2-4 weeks |

---

## Additional Slides for Presentation

### New Slide: Unstructured Data Capabilities

**Title:** Handling Unstructured Data from CMOs

**Content:**

```
┌─────────────────────────────────────────────────────────────┐
│                 UNSTRUCTURED DATA TYPES                      │
│                                                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│   │  DOCUMENTS  │  │   IMAGES    │  │  IOT DATA   │        │
│   │             │  │             │  │             │        │
│   │ • Batch PDFs│  │ • Visual QC │  │ • Sensors   │        │
│   │ • CoAs      │  │ • Labels    │  │ • Equipment │        │
│   │ • Deviations│  │ • Equipment │  │ • Environ.  │        │
│   │             │  │             │  │             │        │
│   │   ┌─────┐   │  │   ┌─────┐   │  │   ┌─────┐   │        │
│   │   │ 📄  │   │  │   │ 🖼️  │   │  │   │ 📊  │   │        │
│   │   └─────┘   │  │   └─────┘   │  │   └─────┘   │        │
│   │             │  │             │  │             │        │
│   │  Textract   │  │ Rekognition │  │  IoT Core   │        │
│   │  Comprehend │  │ Custom      │  │  Timestream │        │
│   │             │  │ Labels      │  │             │        │
│   └─────────────┘  └─────────────┘  └─────────────┘        │
│                           │                                 │
│                           ▼                                 │
│              ┌─────────────────────────┐                   │
│              │    AMAZON BEDROCK       │                   │
│              │    (Generative AI)      │                   │
│              │                         │                   │
│              │  • Document Q&A         │                   │
│              │  • Insight Generation   │                   │
│              │  • Knowledge Assistant  │                   │
│              └─────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

**Key Capabilities:**
- ✅ Extract structured data from PDFs (Textract)
- ✅ Automated visual inspection analysis (Rekognition)
- ✅ Real-time sensor data ingestion (IoT Core)
- ✅ AI-powered document search and Q&A (Bedrock)

*Speaker Notes:*
The solution handles unstructured data as well. For documents like batch records and CoAs, we use Amazon Textract to extract structured data from PDFs. For images from visual inspection, Amazon Rekognition can detect defects using custom-trained models. For IoT sensor data, AWS IoT Core ingests real-time telemetry into Amazon Timestream. And tying it all together, Amazon Bedrock provides generative AI capabilities—enabling natural language queries across all CMO documentation.

---

### New Slide: Generative AI Use Cases

**Title:** AI-Powered Insights with Amazon Bedrock

**Content:**

| Use Case | Description | Business Value |
|----------|-------------|----------------|
| **Document Q&A** | Ask questions about batch records, CoAs, deviations | Faster information retrieval |
| **Deviation Summarization** | Auto-generate summaries of quality events | Reduced manual review time |
| **Cross-CMO Analysis** | Compare quality metrics across manufacturers | Data-driven CMO selection |
| **Knowledge Assistant** | Chatbot for SOPs, procedures, guidelines | Self-service for quality teams |
| **Anomaly Explanation** | AI-generated explanations for process anomalies | Faster root cause analysis |

**Example Interaction:**
```
User: "Show me all temperature excursions at CMO Alpha 
       in the last 30 days and summarize the root causes"

Bedrock: "I found 3 temperature excursions at CMO Alpha:
         1. Jan 15 - Cold room failure (HVAC malfunction)
         2. Jan 22 - Door left open during transfer
         3. Feb 1 - Sensor calibration drift
         
         Common theme: 2 of 3 related to equipment 
         maintenance. Recommend preventive maintenance 
         review with CMO."
```

*Speaker Notes:*
Amazon Bedrock enables powerful generative AI use cases. Quality teams can ask natural language questions about CMO documentation and get instant answers. The system can automatically summarize deviation reports, compare quality metrics across CMOs, and even explain anomalies detected in process data. This transforms how Merck interacts with CMO data—from manual searching to conversational intelligence.

---

## Summary: Complete Data Types Supported

| Data Category | Examples | Ingestion Pattern | Processing Services | Storage |
|---------------|----------|-------------------|---------------------|---------|
| **Structured** | Batch data, quality metrics, equipment logs | Patterns 1-4 | Glue, Athena, Redshift | S3 (Iceberg) |
| **Documents** | PDFs, Word docs, scanned records | Pattern 4, 5 | Textract, Comprehend | S3 + OpenSearch |
| **Images** | Visual inspection, labels, equipment photos | Pattern 4, 5 | Rekognition | S3 + metadata in Glue |
| **Time-Series** | Sensor data, equipment telemetry | Pattern 5 (IoT) | IoT Core, Timestream | Timestream + S3 archive |
| **Semi-Structured** | JSON logs, XML exports, API responses | Patterns 1-4 | Glue, Lambda | S3 (Iceberg) |

---

Would you like me to:

1. **Add these unstructured data slides to the main presentation?**
2. **Create a separate deep-dive appendix on unstructured data processing?**
3. **Develop specific use case scenarios** (e.g., "Day in the life of a Quality Manager using the platform")?
4. **Add cost estimates** for the AI/ML services (Textract, Rekognition, Bedrock)?