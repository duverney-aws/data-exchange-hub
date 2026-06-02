# Updated Presentation with Unstructured Data Slides

I've integrated the unstructured data content into the main presentation. Below is the complete updated slide deck with new slides inserted in logical positions.

---

## Complete Slide Deck: Pharma Data Exchange Hub

---

## Slide 1: Title Slide

**Title:** Pharma Data Exchange Hub

**Subtitle:** Accelerating CMO Data Integration from Months to Days

**Presented by:** [Your Name], AWS Solutions Architect

**Date:** [Date]

**Logo placement:** AWS logo, Merck logo (if permitted)

*Speaker Notes:*
Welcome everyone. Today we'll present our strategic approach to solving Merck's CMO data exchange challenge. Our goal is to reduce data access timelines from months to days using a standardized, pattern-based approach built on AWS services.

---

## Slide 2: Agenda

```
1. Understanding the Challenge
2. Root Cause Analysis
3. Strategic Approach
4. Solution Overview
5. Data Types Supported (Structured + Unstructured)
6. Architecture Patterns (5 Options)
7. Unstructured Data Processing
8. Generative AI Capabilities
9. Unified Control Plane
10. Security & Compliance
11. Implementation Roadmap
12. Success Metrics
13. Next Steps
```

*Speaker Notes:*
Here's our agenda for today. We'll start by framing the problem, then walk through our proposed solution architecture covering both structured and unstructured data, and finish with a clear implementation path.

---

## Slide 3: The Business Challenge

**Title:** Current State: The Data Access Bottleneck

**Content:**

| Challenge | Impact |
|-----------|--------|
| 3-6 month integration timelines | Delayed insights, slower decision-making |
| Custom integration for each CMO | High cost, non-scalable |
| Lengthy legal negotiations | Blocks technical progress |
| Varied CMO technical maturity | No one-size-fits-all solution |
| Multiple data types (structured + unstructured) | Complex integration requirements |

**Key Message Box:**
> "The constraint is **time-to-access**, not technical feasibility"

*Visual suggestion:* Timeline graphic showing current 3-6 month process

*Speaker Notes:*
Let's be clear about the problem we're solving. Merck can integrate with CMOs—the technology exists. The issue is that each integration takes 3-6 months due to legal negotiations, custom technical work, and coordination overhead. This is compounded by the variety of data types CMOs produce—not just structured database records, but documents, images, and sensor data. This delays critical manufacturing insights and creates operational inefficiencies.

---

## Slide 4: Root Cause Analysis

**Title:** Why Does It Take So Long?

**Visual:** Three pillars with time estimates

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│                 │  │                 │  │                 │
│     LEGAL       │  │   TECHNICAL     │  │     TRUST       │
│                 │  │                 │  │                 │
│  • DPA creation │  │  • Discovery    │  │  • Data custody │
│  • Security     │  │  • Custom build │  │    concerns     │
│    review       │  │  • Testing      │  │  • IP protection│
│  • Liability    │  │  • Deployment   │  │  • Audit rights │
│                 │  │                 │  │                 │
│   4-8 weeks     │    4-8 weeks      │  │   Ongoing       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                           │
                           ▼
                    SEQUENTIAL PROCESS
                      = 3-6 MONTHS
```

*Speaker Notes:*
When we analyzed the delays, we found three root causes. First, legal negotiations—every CMO requires custom data processing agreements. Second, technical integration—each CMO has different systems and data types, requiring custom development. Third, trust—CMOs are concerned about data custody and IP protection. These happen sequentially, compounding the delays.

---

## Slide 5: Our Strategic Approach

**Title:** The Solution: Parallelize and Pre-Solve

**Visual:** Before/After comparison

**BEFORE (Sequential):**
```
Legal → Technical Discovery → Custom Build → Test → Production
                        = 3-6 Months
```

**AFTER (Parallel + Pre-Solved):**
```
┌─────────────────────────────────────────────┐
│  Pre-negotiated    +    Standardized    +   │
│  Legal Templates        Patterns            │
│         │                    │              │
│         └────────┬───────────┘              │
│                  ▼                          │
│         Self-Service Onboarding             │
│                  │                          │
│                  ▼                          │
│            = 1-4 Weeks                      │
└─────────────────────────────────────────────┘
```

*Speaker Notes:*
Our approach attacks all three root causes simultaneously. We pre-negotiate legal templates that CMOs can accept quickly. We create standardized integration patterns so there's no custom development. And we build trust infrastructure—like AWS Clean Rooms—that addresses data custody concerns by design. This transforms a sequential 6-month process into a parallel 1-4 week process.

---

## Slide 6: Solution Overview

**Title:** Pharma Data Exchange Hub - Conceptual Architecture

**Visual:** High-level architecture diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CMO ECOSYSTEM                             │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│   │ CMO A   │  │ CMO B   │  │ CMO C   │  │ CMO D   │       │
│   │(Cloud)  │  │(Snowflk)│  │(On-Prem)│  │(Legacy) │       │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
└────────┼────────────┼────────────┼────────────┼─────────────┘
         │            │            │            │
         ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│              PATTERN LIBRARY (Choose Your Path)             │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│   │ Data    │  │ Clean   │  │Snowflake│  │ Secure  │       │
│   │Exchange │  │ Rooms   │  │ Connect │  │Transfer │       │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
│                      ┌─────────┐                            │
│                      │Unstruct.│                            │
│                      │ Data    │                            │
│                      └─────────┘                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 MERCK DATA PLATFORM                          │
│        ┌─────────────────────────────────────┐              │
│        │   Unified Data Lake + Governance    │              │
│        │   + AI/ML Processing                │              │
│        └─────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

**Three Key Components:**
1. **Pattern Library** - Multiple integration options for CMO flexibility (structured + unstructured)
2. **Self-Service Portal** - CMO onboarding without Merck IT bottleneck
3. **Unified Governance + AI** - Consistent security, quality, compliance, and intelligent insights

*Speaker Notes:*
Here's the conceptual architecture. At the top, we have CMOs with varying technical capabilities. In the middle, we offer a pattern library—five standardized ways to connect, including a dedicated pattern for unstructured data like documents, images, and IoT streams. CMOs choose the pattern that fits their infrastructure. At the bottom, all data flows into Merck's unified data platform with consistent governance and AI-powered processing. This design accommodates CMO diversity while giving Merck standardization.

---

## Slide 7: Data Types Supported (NEW)

**Title:** Complete Data Coverage: Structured + Unstructured

**Visual:** Data type matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CMO DATA TYPES SUPPORTED                            │
│                                                                              │
│   STRUCTURED DATA                        UNSTRUCTURED DATA                  │
│   ┌─────────────────────────┐           ┌─────────────────────────┐        │
│   │                         │           │                         │        │
│   │  • Batch Records        │           │  • PDF Documents        │        │
│   │  • Quality Metrics      │           │  • Scanned Records      │        │
│   │  • Equipment Logs       │           │  • Certificates (CoA)   │        │
│   │  • Material Data        │           │  • Deviation Reports    │        │
│   │  • Test Results         │           │  • SOPs                 │        │
│   │                         │           │                         │        │
│   │  ┌─────┐ ┌─────┐       │           │  ┌─────┐ ┌─────┐       │        │
│   │  │ 📊  │ │ 📈  │       │           │  │ 📄  │ │ 📋  │       │        │
│   │  └─────┘ └─────┘       │           │  └─────┘ └─────┘       │        │
│   └─────────────────────────┘           └─────────────────────────┘        │
│                                                                              │
│   IMAGES & MEDIA                         IOT / TIME-SERIES                  │
│   ┌─────────────────────────┐           ┌─────────────────────────┐        │
│   │                         │           │                         │        │
│   │  • Visual Inspection    │           │  • Temperature Sensors  │        │
│   │  • Label Scans          │           │  • Pressure Readings    │        │
│   │  • Equipment Photos     │           │  • Equipment Telemetry  │        │
│   │  • Packaging Images     │           │  • Environmental Data   │        │
│   │  • Training Videos      │           │  • Process Parameters   │        │
│   │                         │           │                         │        │
│   │  ┌─────┐ ┌─────┐       │           │  ┌─────┐ ┌─────┐       │        │
│   │  │ 🖼️  │ │ 🎥  │       │           │  │ 🌡️  │ │ ⚙️  │       │        │
│   │  └─────┘ └─────┘       │           │  └─────┘ └─────┘       │        │
│   └─────────────────────────┘           └─────────────────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Message:**
> "One platform handles ALL CMO data types—not just database exports"

*Speaker Notes:*
A critical aspect of our solution is comprehensive data type coverage. CMOs don't just produce structured database records—they generate PDF batch records, scanned certificates of analysis, visual inspection images, and real-time sensor data. Our platform handles all of these. Structured data flows through patterns 1-4, while unstructured data uses pattern 5 with specialized AI services for extraction and analysis. This eliminates the need for separate integration projects for different data types.

---

## Slide 8: Pattern Overview

**Title:** Five Integration Patterns - Meeting CMOs Where They Are

**Visual:** Pattern matrix

```
                         DATA TYPE
              Structured ◄─────────► Unstructured
          ┌─────────────────────────────────────────┐
          │                                         │
   High   │  Pattern 1        │     Pattern 5      │
          │  AWS Data         │     Unstructured   │
   CMO    │  Exchange         │     (Docs/Images/  │
   Cloud  │                   │      IoT)          │
   Maturity├───────────────────┼────────────────────┤
          │  Pattern 2        │     Pattern 5      │
   Low    │  Clean Rooms      │     Unstructured   │
          │  ─────────────────│                    │
          │  Pattern 3        │                    │
          │  Snowflake        │                    │
          │  ─────────────────│                    │
          │  Pattern 4        │                    │
          │  Secure Transfer  │◄── Also handles   │
          │                   │    unstructured   │
          └─────────────────────────────────────────┘
```

| Pattern | Data Type | Best For | Time to Value |
|---------|-----------|----------|---------------|
| 1. AWS Data Exchange | Structured | Cloud-native CMOs | 1-2 weeks |
| 2. AWS Clean Rooms | Structured | Privacy-sensitive | 2-3 weeks |
| 3. Snowflake Integration | Structured | Snowflake CMOs | 1-2 weeks |
| 4. Secure File Transfer | Structured + Unstructured | Legacy/on-prem | 2-4 weeks |
| 5. Unstructured Data | Documents, Images, IoT | All CMOs | 2-4 weeks |

*Speaker Notes:*
We've designed five patterns to accommodate different CMO situations and data types. Patterns 1-3 focus on structured data with varying levels of cloud maturity and privacy requirements. Pattern 4 handles both structured and unstructured files via secure transfer—ideal for legacy environments. Pattern 5 is dedicated to unstructured data processing with AI services. Most CMOs will use a combination—for example, Pattern 1 for structured data plus Pattern 5 for document processing.

---

## Slide 9: Pattern 1 - AWS Data Exchange

**Title:** Pattern 1: AWS Data Exchange (Publisher/Subscriber)

**Visual:** Architecture diagram

```
┌──────────────────┐         ┌──────────────────┐
│   CMO Account    │         │  Merck Account   │
│  ┌────────────┐  │         │  ┌────────────┐  │
│  │ Mfg Data   │  │         │  │ S3 Landing │  │
│  └─────┬──────┘  │         │  │ Zone       │  │
│        │         │         │  └─────▲──────┘  │
│        ▼         │         │        │         │
│  ┌────────────┐  │  AWS    │        │         │
│  │ Publish to │  │  Data   │  ┌─────┴──────┐  │
│  │ Data Exch  │──┼─Exchange┼─▶│ Subscribe  │  │
│  │ (Private)  │  │         │  │ (Entitled) │  │
│  └────────────┘  │         │  └────────────┘  │
└──────────────────┘         └──────────────────┘
```

**Key Benefits:**
- ✅ Managed data marketplace - no infrastructure to build
- ✅ Private offers - data only visible to Merck
- ✅ Automatic updates - subscribe once, receive continuously
- ✅ Built-in entitlements and access control

**AWS Services:** AWS Data Exchange, S3, Glue, Lake Formation

**Data Types:** Structured (CSV, Parquet, JSON)

*Speaker Notes:*
Pattern 1 uses AWS Data Exchange, which is essentially a managed data marketplace. CMOs publish datasets as private offers visible only to Merck. Merck subscribes and automatically receives updates. This is ideal for CMOs already comfortable with cloud and willing to push structured data. The advantage is minimal infrastructure—AWS manages the exchange mechanics.

---

## Slide 10: Pattern 2 - AWS Clean Rooms

**Title:** Pattern 2: AWS Clean Rooms (Privacy-Preserving Collaboration)

**Visual:** Architecture diagram

```
┌──────────────────┐         ┌──────────────────┐
│   CMO Account    │         │  Merck Account   │
│  ┌────────────┐  │         │  ┌────────────┐  │
│  │ Mfg Data   │  │         │  │ Quality    │  │
│  │ (Stays     │  │         │  │ Data       │  │
│  │  Here!)    │  │         │  └─────┬──────┘  │
│  └─────┬──────┘  │         │        │         │
│        │         │         │        │         │
│        ▼         │         │        ▼         │
│  ┌────────────┐  │         │  ┌────────────┐  │
│  │ Configured │◀─┼─────────┼─▶│ Configured │  │
│  │ Table      │  │  CLEAN  │  │ Table      │  │
│  └────────────┘  │  ROOM   │  └────────────┘  │
└──────────────────┘    │    └──────────────────┘
                        ▼
               ┌─────────────────┐
               │ Aggregated      │
               │ Results Only    │
               │ (No Raw Data)   │
               └─────────────────┘
```

**Key Benefits:**
- ✅ Data never leaves CMO's account
- ✅ Only approved queries can run
- ✅ Results are aggregated - no row-level exposure
- ✅ Addresses IP and custody concerns

**AWS Services:** AWS Clean Rooms, S3, Glue Data Catalog

**Data Types:** Structured (tables)

*Speaker Notes:*
Pattern 2 is our answer to the trust problem. With Clean Rooms, CMO data never leaves their AWS account. Instead, both parties configure tables in a shared collaboration. Only pre-approved queries can run, and results are aggregated—no raw data exposed. This is powerful for CMOs who say "we can't let our data leave our control." With Clean Rooms, it doesn't have to.

---

## Slide 11: Pattern 3 - Snowflake Integration

**Title:** Pattern 3: Snowflake Integration (Platform Accommodation)

**Visual:** Architecture diagram

```
┌──────────────────┐         ┌──────────────────┐
│  CMO Snowflake   │         │  Merck AWS       │
│  ┌────────────┐  │         │  ┌────────────┐  │
│  │ Mfg Data   │  │         │  │ Option A:  │  │
│  │ Tables     │  │         │  │ Snowflake  │  │
│  └─────┬──────┘  │         │  │ Reader Acct│  │
│        │         │         │  └────────────┘  │
│        ▼         │         │        OR        │
│  ┌────────────┐  │ Secure  │  ┌────────────┐  │
│  │ Snowflake  │  │ Share   │  │ Option B:  │  │
│  │ Secure     │──┼─────────┼─▶│ S3 External│  │
│  │ Data Share │  │   or    │  │ Stage +    │  │
│  └────────────┘  │ S3 Stage│  │ Glue       │  │
│                  │         │  └────────────┘  │
└──────────────────┘         └──────────────────┘
```

**Key Benefits:**
- ✅ Leverages CMO's existing Snowflake investment
- ✅ Native Snowflake sharing - zero copy, instant access
- ✅ Alternative S3 stage for AWS-native consumption
- ✅ Minimal CMO effort - they already know Snowflake

**AWS Services:** S3, Glue (Snowflake connector), PrivateLink

**Data Types:** Structured (Snowflake tables)

*Speaker Notes:*
Many CMOs have already invested in Snowflake. Pattern 3 meets them where they are. CMOs can use Snowflake's native secure data sharing to give Merck access—either through a Snowflake reader account or by staging to S3 for AWS-native consumption. This pattern has the fastest time-to-value for Snowflake CMOs because we're leveraging capabilities they already have.

---

## Slide 12: Pattern 4 - Secure File Transfer

**Title:** Pattern 4: Secure File Transfer (Legacy/On-Prem CMOs)

**Visual:** Architecture diagram

```
┌──────────────────┐         ┌──────────────────────────────┐
│  CMO On-Premises │         │       Merck AWS Account      │
│  ┌────────────┐  │         │  ┌─────────────────────────┐ │
│  │ MES/ERP    │  │         │  │  AWS Transfer Family    │ │
│  │ System     │  │  SFTP   │  │  ┌─────────────────┐    │ │
│  └─────┬──────┘  │  over   │  │  │ Managed SFTP    │    │ │
│        │         │  VPN    │  │  │ Endpoint        │    │ │
│        ▼         │         │  │  └────────┬────────┘    │ │
│  ┌────────────┐  │         │  └───────────┼─────────────┘ │
│  │ Export     │──┼─────────┼──────────────┘               │
│  │ Files      │  │         │              │               │
│  │ (CSV/PDF/  │  │         │              ▼               │
│  │  Images)   │  │         │  ┌─────────────────────────┐ │
│  └────────────┘  │         │  │ S3 → EventBridge →      │ │
└──────────────────┘         │  │ Step Functions →        │ │
                             │  │ Processing Pipeline     │ │
        ┌────────────┐       │  └─────────────────────────┘ │
        │ Direct     │       └──────────────────────────────┘
        │ Connect/VPN│───────
        └────────────┘
```

**Key Benefits:**
- ✅ Works with any CMO - no cloud required
- ✅ Handles BOTH structured AND unstructured files
- ✅ Familiar protocol (SFTP) - minimal CMO training
- ✅ Event-driven processing - automatic on file arrival

**AWS Services:** Transfer Family, Direct Connect/VPN, S3, EventBridge, Step Functions, Glue

**Data Types:** Structured (CSV, JSON) + Unstructured (PDF, Images)

*Speaker Notes:*
Pattern 4 is our universal fallback and the most flexible pattern. Some CMOs have limited cloud maturity or regulatory constraints. For them, we offer managed SFTP through AWS Transfer Family. CMOs export files—both structured data files AND unstructured documents like PDFs and images—and upload via SFTP over a secure VPN connection. On the AWS side, file arrival triggers automated processing. This pattern handles the widest variety of data types.

---

## Slide 13: Pattern 5 - Unstructured Data Processing (NEW)

**Title:** Pattern 5: Unstructured Data Processing (Documents, Images, IoT)

**Visual:** Architecture diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PATTERN 5: UNSTRUCTURED DATA PROCESSING                  │
│                                                                              │
│   CMO DATA SOURCES                                                          │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│   │  Batch  │  │  CoA    │  │ Visual  │  │  IoT    │  │  Lab    │          │
│   │ Records │  │  PDFs   │  │ Inspect │  │ Sensors │  │ Instrum │          │
│   │ (PDF)   │  │         │  │ Images  │  │         │  │  Files  │          │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘          │
│        └────────────┴────────────┼────────────┴────────────┘               │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    INGESTION (Transfer Family / IoT Core)            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    AI PROCESSING PIPELINE                            │   │
│   │                                                                      │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│   │   │  Amazon     │  │  Amazon     │  │  Amazon     │                 │   │
│   │   │  Textract   │  │  Rekognition│  │  Comprehend │                 │   │
│   │   │  (OCR/Forms)│  │  (Images)   │  │  (NLP)      │                 │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                 │   │
│   │                                                                      │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│   │   │  AWS IoT    │  │  Amazon     │  │  Amazon     │                 │   │
│   │   │  Core       │  │  Timestream │  │  Bedrock    │                 │   │
│   │   │  (Sensors)  │  │  (Time-Ser.)│  │  (Gen AI)   │                 │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                 │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   OUTPUTS: Structured metadata + Searchable index + AI insights     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- ✅ Extracts structured data from unstructured sources
- ✅ AI-powered document understanding
- ✅ Real-time IoT data ingestion
- ✅ Enables search and Gen AI across all CMO content

**AWS Services:** Textract, Rekognition, Comprehend, IoT Core, Timestream, Bedrock, OpenSearch

*Speaker Notes:*
Pattern 5 is dedicated to unstructured data—the documents, images, and sensor streams that CMOs produce alongside structured records. When a PDF batch record arrives, Amazon Textract extracts tables and form fields into structured JSON. Visual inspection images go through Amazon Rekognition for defect detection. IoT sensor data streams through AWS IoT Core into Amazon Timestream. All content is indexed in OpenSearch for search, and Amazon Bedrock enables generative AI capabilities like document Q&A. This pattern transforms unstructured data into actionable intelligence.

---

## Slide 14: Document Processing Deep Dive (NEW)

**Title:** Document Processing: From PDFs to Structured Data

**Visual:** Processing pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DOCUMENT PROCESSING PIPELINE                             │
│                                                                              │
│   INPUT                    PROCESSING                      OUTPUT           │
│                                                                              │
│   ┌─────────────┐         ┌─────────────────────┐         ┌─────────────┐   │
│   │             │         │                     │         │             │   │
│   │  Batch      │         │   Amazon Textract   │         │ Structured  │   │
│   │  Record     │────────▶│                     │────────▶│ JSON:       │   │
│   │  (PDF)      │         │   • OCR             │         │             │   │
│   │             │         │   • Table Extract   │         │ • Batch ID  │   │
│   │  ┌───────┐  │         │   • Form Extract    │         │ • Product   │   │
│   │  │ 📄    │  │         │   • Signature Det.  │         │ • Yield     │   │
│   │  └───────┘  │         │                     │         │ • Parameters│   │
│   └─────────────┘         └─────────────────────┘         └──────┬──────┘   │
│                                                                  │          │
│   ┌─────────────┐         ┌─────────────────────┐                │          │
│   │             │         │                     │                │          │
│   │  CoA        │         │  Amazon Comprehend  │                │          │
│   │  (PDF)      │────────▶│                     │────────────────┤          │
│   │             │         │   • Entity Extract  │                │          │
│   │  ┌───────┐  │         │   • Key Phrases     │                │          │
│   │  │ 📋    │  │         │   • Sentiment       │                │          │
│   │  └───────┘  │         │                     │                │          │
│   └─────────────┘         └─────────────────────┘                │          │
│                                                                  ▼          │
│                                                          ┌─────────────┐   │
│                                                          │             │   │
│                                                          │ • S3 (JSON) │   │
│                                                          │ • OpenSearch│   │
│                                                          │   (Index)   │   │
│                                                          │ • Glue      │   │
│                                                          │   (Catalog) │   │
│                                                          │             │   │
│                                                          └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Supported Document Types:**
| Document | Extraction | Use Case |
|----------|------------|----------|
| Batch Records | Tables, forms, signatures | Compliance, trending |
| Certificates of Analysis | Test results, specifications | Quality release |
| Deviation Reports | Root cause, CAPA actions | Quality metrics |
| SOPs | Procedures, version info | Knowledge management |

*Speaker Notes:*
Let's dive deeper into document processing. When a PDF batch record arrives from a CMO, Amazon Textract performs OCR and intelligently extracts tables and form fields. For example, it can pull out batch ID, product name, yield percentages, and process parameters—converting a scanned document into structured, queryable data. Amazon Comprehend adds natural language processing to extract entities and key phrases. The output is stored as JSON in S3, indexed in OpenSearch for search, and cataloged in Glue for analytics. This means quality teams can query across all CMO batch records without manually reading PDFs.

---

## Slide 15: Image Analysis Deep Dive (NEW)

**Title:** Image Analysis: AI-Powered Visual Quality Control

**Visual:** Processing pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IMAGE ANALYSIS PIPELINE                                  │
│                                                                              │
│   INPUT                    PROCESSING                      OUTPUT           │
│                                                                              │
│   ┌─────────────┐         ┌─────────────────────┐         ┌─────────────┐   │
│   │             │         │                     │         │             │   │
│   │  Visual     │         │ Amazon Rekognition  │         │ Analysis    │   │
│   │  Inspection │────────▶│                     │────────▶│ Results:    │   │
│   │  Image      │         │ Custom Labels       │         │             │   │
│   │             │         │ (Trained on pharma  │         │ • Defect: Y │   │
│   │  ┌───────┐  │         │  defect types)      │         │ • Type: Crack│  │
│   │  │ 🖼️    │  │         │                     │         │ • Confidence│   │
│   │  └───────┘  │         │ • Defect detection  │         │   : 94.2%   │   │
│   └─────────────┘         │ • Classification    │         │ • Location  │   │
│                           │ • Bounding boxes    │         │             │   │
│   ┌─────────────┐         └─────────────────────┘         └──────┬──────┘   │
│   │             │                                                │          │
│   │  Label      │         ┌─────────────────────┐                │          │
│   │  Scan       │────────▶│                     │                │          │
│   │             │         │ Amazon Rekognition  │────────────────┤          │
│   │  ┌───────┐  │         │                     │                │          │
│   │  │ 🏷️    │  │         │ • Text detection    │                │          │
│   │  └───────┘  │         │ • Label verification│                │          │
│   └─────────────┘         │                     │                │          │
│                           └─────────────────────┘                │          │
│                                                                  ▼          │
│                                                          ┌─────────────┐   │
│                                                          │ • Alert if  │   │
│                                                          │   defect    │   │
│                                                          │ • Store     │   │
│                                                          │   metadata  │   │
│                                                          │ • Dashboard │   │
│                                                          │   metrics   │   │
│                                                          └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Use Cases:**
| Image Type | Analysis | Business Value |
|------------|----------|----------------|
| Visual Inspection | Defect detection, classification | Automated QC, reduced manual review |
| Label Scans | Text verification, compliance check | Regulatory compliance |
| Equipment Photos | Condition assessment | Predictive maintenance |
| Packaging | Integrity verification | Quality assurance |

*Speaker Notes:*
For image analysis, we use Amazon Rekognition with Custom Labels. This allows us to train models specifically on pharmaceutical defect types—cracks, discoloration, contamination, whatever is relevant to Merck's products. When a visual inspection image arrives from a CMO, the model analyzes it and returns whether a defect was detected, what type, confidence score, and location in the image. For label scans, Rekognition can verify that text matches expected values. This enables automated quality control at scale—instead of manual review of every image, the system flags only those requiring human attention.

---

## Slide 16: IoT/Time-Series Data Deep Dive (NEW)

**Title:** IoT Data: Real-Time Sensor Ingestion

**Visual:** Processing pipeline

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
│   │        └────────────┴─────┬──────┴────────────┘                    │   │
│   │                           │                                        │   │
│   │                    ┌──────▼──────┐                                 │   │
│   │                    │ IoT Gateway │                                 │   │
│   │                    └──────┬──────┘                                 │   │
│   └───────────────────────────┼─────────────────────────────────────────┘   │
│                               │  MQTT / HTTPS                               │
│                               ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      AWS IOT CORE                                    │   │
│   │   • Device authentication    • Message routing                      │   │
│   │   • Protocol translation     • Rules engine                         │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                          │
│              ┌───────────────────┼───────────────────┐                     │
│              ▼                   ▼                   ▼                     │
│   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐             │
│   │ Amazon          │ │ Amazon Kinesis  │ │ Amazon S3       │             │
│   │ Timestream      │ │ Data Firehose   │ │ (Raw Archive)   │             │
│   │ (Query/Alert)   │ │ (Transform)     │ │                 │             │
│   └────────┬────────┘ └────────┬────────┘ └─────────────────┘             │
│            │                   │                                           │
│            └─────────┬─────────┘                                           │
│                      ▼                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  ANALYTICS: Grafana Dashboards │ Anomaly Detection │ Alerts         │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Sensor Data Types:**
| Sensor | Frequency | Use Case |
|--------|-----------|----------|
| Temperature | Every 1-5 min | Cold chain monitoring, process control |
| Pressure | Every 1-5 min | Reactor monitoring, HVAC |
| Humidity | Every 5-15 min | Environmental monitoring |
| Vibration | Every 1 min | Equipment health, predictive maintenance |
| Flow Rate | Every 1 min | Process control |

*Speaker Notes:*
For IoT and time-series data, we use AWS IoT Core as the ingestion point. CMO sensors connect through an IoT gateway and stream data via MQTT or HTTPS. IoT Core handles device authentication, protocol translation, and message routing. Data flows to Amazon Timestream—a purpose-built time-series database optimized for sensor data queries. We also archive raw data to S3 for long-term retention. Amazon Managed Grafana provides real-time dashboards, and we can configure anomaly detection to alert when sensor readings exceed thresholds. This gives Merck real-time visibility into CMO manufacturing conditions.

---

## Slide 17: Generative AI Capabilities (NEW)

**Title:** AI-Powered Insights with Amazon Bedrock

**Visual:** Gen AI use cases

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GENERATIVE AI LAYER (Amazon Bedrock)                     │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    KNOWLEDGE BASE (RAG Architecture)                 │   │
│   │                                                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  Indexed CMO Data                                            │   │   │
│   │   │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │   │   │
│   │   │  │  Batch  │  │  SOPs   │  │Deviation│  │  CoAs   │        │   │   │
│   │   │  │ Records │  │         │  │ Reports │  │         │        │   │   │
│   │   │  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                              │                                      │   │
│   │                              ▼                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  Vector Store (OpenSearch Serverless)                        │   │   │
│   │   │  • Document embeddings • Semantic search                     │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    USE CASES                                         │   │
│   │                                                                      │   │
│   │   ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────┐ │   │
│   │   │   DOCUMENT Q&A    │  │ DEVIATION SUMMARY │  │ CROSS-CMO       │ │   │
│   │   │                   │  │                   │  │ ANALYSIS        │ │   │
│   │   │ "What was the     │  │ "Summarize all    │  │ "Compare yield  │ │   │
│   │   │  yield for batch  │  │  temperature      │  │  trends across  │ │   │
│   │   │  ABC-123?"        │  │  excursions at    │  │  CMO A, B, C"   │ │   │
│   │   │                   │  │  CMO Alpha"       │  │                 │ │   │
│   │   └───────────────────┘  └───────────────────┘  └─────────────────┘ │   │
│   │                                                                      │   │
│   │   ┌───────────────────┐  ┌───────────────────┐                      │   │
│   │   │ KNOWLEDGE         │  │ ANOMALY           │                      │   │
│   │   │ ASSISTANT         │  │ EXPLANATION       │                      │   │
│   │   │                   │  │                   │                      │   │
│   │   │ "What's the SOP   │  │ "Why did reactor  │                      │   │
│   │   │  for handling     │  │  pressure spike   │                      │   │
│   │   │  OOS results?"    │  │  on Jan 15?"      │                      │   │
│   │   └───────────────────┘  └───────────────────┘                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Foundation Models Available:**
- **Claude (Anthropic)** - Document analysis, summarization, reasoning
- **Titan (Amazon)** - Embeddings, text generation
- **Llama (Meta)** - General purpose, cost-effective

*Speaker Notes:*
Amazon Bedrock brings generative AI capabilities to the platform. We build a knowledge base using RAG—Retrieval Augmented Generation—that indexes all CMO documents, batch records, and quality data. Users can then ask natural language questions and get accurate, sourced answers. For example, "What was the yield for batch ABC-123?" or "Summarize all temperature excursions at CMO Alpha last quarter." The system retrieves relevant documents, passes them to a foundation model like Claude, and generates a response with citations. This transforms how quality teams interact with CMO data—from searching through documents to having a conversation.

---

## Slide 18: Gen AI Example Interaction (NEW)

**Title:** Generative AI in Action

**Visual:** Example conversation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXAMPLE: QUALITY MANAGER INTERACTION                     │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  👤 USER QUERY                                                       │   │
│   │                                                                      │   │
│   │  "Show me all temperature excursions at CMO Alpha in the last       │   │
│   │   30 days and summarize the root causes"                            │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  🔍 SYSTEM PROCESSING                                                │   │
│   │                                                                      │   │
│   │  1. Query vector store for "temperature excursion" + "CMO Alpha"   │   │
│   │  2. Retrieve relevant deviation reports (3 found)                   │   │
│   │  3. Pass documents to Claude model with summarization prompt        │   │
│   │  4. Generate response with citations                                │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  🤖 AI RESPONSE                                                      │   │
│   │                                                                      │   │
│   │  "I found 3 temperature excursions at CMO Alpha in the last 30     │   │
│   │   days:                                                             │   │
│   │                                                                      │   │
│   │   1. **Jan 15** - Cold room #2 exceeded 8°C for 45 minutes         │   │
│   │      Root cause: HVAC compressor failure                            │   │
│   │      CAPA: Preventive maintenance schedule updated                  │   │
│   │      [Source: DEV-2024-0142]                                        │   │
│   │                                                                      │   │
│   │   2. **Jan 22** - Warehouse zone B reached 27°C                    │   │
│   │      Root cause: Loading dock door left open during delivery        │   │
│   │      CAPA: Door interlock system installed                          │   │
│   │      [Source: DEV-2024-0156]                                        │   │
│   │                                                                      │   │
│   │   3. **Feb 1** - Lab refrigerator showed 10°C reading              │   │
│   │      Root cause: Temperature sensor calibration drift               │   │
│   │      CAPA: Sensor replaced, calibration frequency increased         │   │
│   │      [Source: DEV-2024-0167]                                        │   │
│   │                                                                      │   │
│   │   **Summary**: 2 of 3 excursions (67%) related to equipment        │   │
│   │   maintenance issues. Recommend reviewing CMO Alpha's preventive   │   │
│   │   maintenance program during next QBR."                             │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Business Value:**
- ⏱️ Minutes instead of hours to find and analyze information
- 📊 AI-generated insights surface patterns humans might miss
- 📎 Every answer includes source citations for verification
- 🔄 Continuous learning as more CMO data is indexed

*Speaker Notes:*
Here's a concrete example of generative AI in action. A quality manager asks about temperature excursions at a specific CMO. The system searches the vector store, retrieves relevant deviation reports, and passes them to Claude. The response includes not just a list of events, but a summary of root causes, CAPA actions, and even a recommendation based on pattern analysis. Every statement is linked to a source document for verification. What would have taken hours of manual document review now takes seconds—and the AI surfaces insights like "67% related to equipment maintenance" that might be missed in manual review.

---

## Slide 19: Pattern Selection Guide (UPDATED)

**Title:** Choosing the Right Pattern(s)

**Visual:** Decision tree

```
                    ┌─────────────────────────────────┐
                    │     What data types does the    │
                    │     CMO need to share?          │
                    └────────────────┬────────────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              │                                             │
              ▼                                             ▼
    ┌─────────────────────┐                    ┌─────────────────────┐
    │   STRUCTURED DATA   │                    │  UNSTRUCTURED DATA  │
    │   (DB exports,      │                    │  (PDFs, images,     │
    │    metrics, logs)   │                    │   IoT, documents)   │
    └──────────┬──────────┘                    └──────────┬──────────┘
               │                                          │
               ▼                                          │
    ┌─────────────────────┐                               │
    │ Does CMO have AWS   │                               │
    │ account?            │                               │
    └──────────┬──────────┘                               │
               │                                          │
    ┌──────────┴──────────┐                               │
    │ YES            NO   │                               │
    ▼                ▼    │                               │
┌────────┐    ┌──────────┐│                               │
│Privacy │    │Snowflake?││                               │
│concerns│    └────┬─────┘│                               │
└───┬────┘         │      │                               │
    │       ┌──────┴──────┐                               │
┌───┴───┐   │ YES     NO  │                               │
│  YES  │   ▼         ▼   │                               │
│   │   │┌──────┐ ┌──────┐│                               │
│   ▼   ││Pat.3 │ │Pat.4 ││                               │
│┌──────┐│Snowflk│ │SFTP  ││                               │
││Pat.2 │└──────┘ └──────┘│                               │
││Clean │                 │                               │
││Rooms │                 │                               │
│└──────┘                 │                               │
│   NO                    │                               │
│   │                     │                               │
│   ▼                     │                               ▼
│┌──────┐                 │                        ┌─────────────┐
││Pat.1 │                 │                        │  Pattern 5  │
││Data  │                 │                        │ Unstructured│
││Exch. │                 │                        │ (Always add │
│└──────┘                 │                        │  if needed) │
└─────────────────────────┘                        └─────────────┘
```

**Common Pattern Combinations:**
| CMO Profile | Structured Pattern | Unstructured Pattern |
|-------------|-------------------|---------------------|
| Cloud-native, full data sharing | Pattern 1 (Data Exchange) | Pattern 5 (AI Processing) |
| Cloud-native, privacy concerns | Pattern 2 (Clean Rooms) | Pattern 5 (AI Processing) |
| Snowflake user | Pattern 3 (Snowflake) | Pattern 5 (AI Processing) |
| Legacy/on-prem | Pattern 4 (SFTP) | Pattern 4 + 5 (SFTP + AI) |

*Speaker Notes:*
Most CMOs will use a combination of patterns. This decision tree helps select the right mix. First, identify what data types the CMO needs to share. For structured data, follow the left branch based on cloud maturity and privacy requirements. For unstructured data, Pattern 5 is almost always added. For example, a cloud-native CMO might use Pattern 1 for structured batch data AND Pattern 5 for PDF batch records and visual inspection images. A legacy CMO might use Pattern 4 for everything—SFTP handles both structured files and documents—with Pattern 5's AI processing applied after ingestion.

---

## Slide 20: Unified Control Plane

**Title:** Pharma Data Exchange Hub - Control Plane

**Visual:** Layered architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  SELF-SERVICE PORTAL                         │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│   │   CMO   │  │Connection│  │  Data   │  │Agreement│       │
│   │Onboard  │  │ Wizard   │  │ Catalog │  │Templates│       │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
│                    AWS Amplify + Cognito                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  INTEGRATION LAYER                           │
│            ┌─────────────────────────────┐                  │
│            │      API Gateway            │                  │
│            └─────────────────────────────┘                  │
│   ┌────────┬────────┬────────┬────────┬────────┐           │
│   │Pat. 1  │Pat. 2  │Pat. 3  │Pat. 4  │Pat. 5  │           │
│   │Data Ex │Clean Rm│Snowflk │Transfer│Unstruct│           │
│   └────────┴────────┴────────┴────────┴────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  AI PROCESSING LAYER                         │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│   │Textract │  │Rekognit.│  │Comprehnd│  │ Bedrock │       │
│   │(Docs)   │  │(Images) │  │ (NLP)   │  │ (GenAI) │       │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  GOVERNANCE LAYER                            │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│   │  Lake   │  │  Glue   │  │  Cloud  │  │  Macie  │       │
│   │Formation│  │ Quality │  │  Trail  │  │(PII Det)│       │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  UNIFIED DATA LAKE                           │
│   ┌───────────────────────────────────────────────────────┐ │
│   │                    Amazon S3                           │ │
│   │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │ │
│   │  │ Bronze  │─▶│ Silver  │─▶│  Gold   │  │Unstructd│  │ │
│   │  │  (Raw)  │  │(Curated)│  │(Consume)│  │ (Docs/  │  │ │
│   │  │         │  │         │  │         │  │  Media) │  │ │
│   │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │ │
│   └───────────────────────────────────────────────────────┘ │
│                    + OpenSearch (Search) + Timestream (IoT) │
└─────────────────────────────────────────────────────────────┘
```

*Speaker Notes:*
Regardless of which pattern a CMO uses, all data flows through a unified control plane. At the top, a self-service portal lets CMOs onboard themselves and select their integration patterns. The integration layer provides consistent APIs across all five patterns. The AI processing layer applies Textract, Rekognition, Comprehend, and Bedrock to extract intelligence from unstructured data. The governance layer enforces security, quality, and compliance. At the bottom, all data lands in a unified data lake—structured data in Bronze/Silver/Gold zones, unstructured content indexed in OpenSearch, and time-series data in Timestream. This gives Merck a single, governed, intelligent view of all CMO data.

---

## Slide 21: Accelerator #1 - Legal Templates

**Title:** Accelerator: Pre-Negotiated Legal Framework

**Visual:** Process comparison

**BEFORE:**
```
┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐
│ Draft  │──▶│ Review │──▶│Negotiate──▶│ Sign   │
│ DPA    │   │ (Legal)│   │ Terms  │   │        │
└────────┘   └────────┘   └────────┘   └────────┘
    │            │            │            │
    └────────────┴────────────┴────────────┘
                 4-8 WEEKS
```

**AFTER:**
```
┌─────────────────────────────────────────────────┐
│         PRE-APPROVED TEMPLATE LIBRARY           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │   DPA   │  │Security │  │Liability│         │
│  │Template │  │Addendum │  │ Terms   │         │
│  └─────────┘  └─────────┘  └─────────┘         │
└─────────────────────────────────────────────────┘
                      │
                      ▼
              ┌─────────────┐
              │  DocuSign   │
              │  (e-Sign)   │
              └─────────────┘
                      │
                      ▼
               < 1 WEEK
```

**Template Components:**
- Data Processing Agreement (DPA) - GDPR/CCPA compliant
- Security Addendum - AWS shared responsibility model
- Liability & Indemnification - Pre-negotiated terms
- Data Retention & Deletion - Standard policies
- **AI/ML Processing Consent** - Covers Textract, Rekognition, Bedrock usage

*Speaker Notes:*
Legal negotiation is often the longest delay. Our accelerator: pre-negotiate template agreements that CMOs can accept with minimal modification. We work with Merck Legal to create a library of pre-approved templates covering data processing, security, and liability. Importantly, we include consent for AI/ML processing—covering the use of services like Textract and Bedrock on CMO data. CMOs review and e-sign through DocuSign integration. This reduces legal cycles from 4-8 weeks to under a week for most CMOs.

---

## Slide 22: Accelerator #2 - Self-Service Onboarding

**Title:** Accelerator: CMO Self-Service Onboarding

**Visual:** Onboarding workflow

```
┌─────────────────────────────────────────────────────────────┐
│                  CMO ONBOARDING JOURNEY                      │
│                                                              │
│  STEP 1           STEP 2           STEP 3           STEP 4  │
│ ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐ │
│ │Register│      │ Select │      │Configure│     │ Test & │ │
│ │& Verify│─────▶│Patterns│─────▶│Connect │─────▶│Validate│ │
│ └────────┘      └────────┘      └────────┘      └────────┘ │
│     │               │               │               │       │
│     ▼               ▼               ▼               ▼       │
│ ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐ │
│ │Cognito │      │Pattern │      │CloudFmt│      │Auto    │ │
│ │Identity│      │Wizard  │      │Deploy  │      │Quality │ │
│ │Pool    │      │(1-5)   │      │        │      │Checks  │ │
│ └────────┘      └────────┘      └────────┘      └────────┘ │
│                                                              │
│  ◀──────────────── 1-3 DAYS ────────────────▶              │
└─────────────────────────────────────────────────────────────┘
```

**Key Capabilities:**
- ✅ CMO self-registration with identity verification
- ✅ Guided pattern selection wizard (structured + unstructured)
- ✅ Automated infrastructure deployment (CloudFormation)
- ✅ Built-in data quality validation
- ✅ AI processing pipeline auto-configuration
- ✅ No Merck IT bottleneck

*Speaker Notes:*
The second accelerator is self-service onboarding. CMOs don't wait for Merck IT availability. They register through a portal, verify their identity, and use a wizard to select their integration patterns—including options for unstructured data. Behind the scenes, CloudFormation templates automatically deploy the required infrastructure, including AI processing pipelines for documents and images. Built-in data quality checks validate the connection. The entire technical onboarding can happen in 1-3 days without Merck IT involvement.

---

## Slide 23: Accelerator #3 - Pharma Data Standards

**Title:** Accelerator: Pre-Built Pharma Data Models

**Visual:** Schema library

```
┌─────────────────────────────────────────────────────────────┐
│              PHARMA DATA MODEL LIBRARY                       │
│                  (Glue Data Catalog)                         │
│                                                              │
│  STRUCTURED MODELS                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   BATCH     │  │  EQUIPMENT  │  │   QUALITY   │         │
│  │  RECORDS    │  │    DATA     │  │   EVENTS    │         │
│  │ • Batch ID  │  │ • Asset ID  │  │ • Deviation │         │
│  │ • Product   │  │ • Location  │  │ • CAPA      │         │
│  │ • Yield     │  │ • Status    │  │ • OOS       │         │
│  │ (ISA-88)    │  │             │  │             │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  UNSTRUCTURED EXTRACTION TEMPLATES                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ BATCH PDF   │  │    CoA      │  │  DEVIATION  │         │
│  │  TEMPLATE   │  │  TEMPLATE   │  │  TEMPLATE   │         │
│  │             │  │             │  │             │         │
│  │ • Header    │  │ • Product   │  │ • Event ID  │         │
│  │   fields    │  │ • Tests     │  │ • Root cause│         │
│  │ • Process   │  │ • Results   │  │ • CAPA      │         │
│  │   params    │  │ • Specs     │  │ • Status    │         │
│  │ • Signatures│  │ • Approval  │  │             │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  Format: Apache Iceberg (schema evolution supported)        │
└─────────────────────────────────────────────────────────────┘
```

**Benefits:**
- CMOs map their data to standard schemas
- Textract extraction templates pre-configured for common document types
- Merck consumes consistent data regardless of source
- Schema evolution handles changes without breaking pipelines

*Speaker Notes:*
The third accelerator is pre-built pharma data models—for both structured AND unstructured data. For structured data, we define industry-standard models for batch records, equipment data, and quality events. For unstructured data, we create Textract extraction templates for common document types like batch record PDFs and Certificates of Analysis. These templates tell Textract exactly which fields to extract and how to structure the output. CMOs don't need to define schemas from scratch—they map to our standards. Merck always receives data in a consistent format.

---

## Slide 24: Security & Compliance

**Title:** Security & Compliance Architecture

**Visual:** Security layers

```
┌─────────────────────────────────────────────────────────────┐
│                 IDENTITY & ACCESS                            │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ IAM       │  │   AWS     │  │ Attribute │               │
│  │ Identity  │  │   Orgs    │  │ Based     │               │
│  │ Center    │  │(Multi-Acc)│  │ Access    │               │
│  └───────────┘  └───────────┘  └───────────┘               │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                 DATA PROTECTION                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │
│  │  AWS KMS  │  │ S3 Object │  │   Macie   │  │  Clean   │ │
│  │ (CMK per  │  │   Lock    │  │ (PII      │  │  Rooms   │ │
│  │   CMO)    │  │  (WORM)   │  │  Detect)  │  │ (Privacy)│ │
│  └───────────┘  └───────────┘  └───────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                 AI/ML GOVERNANCE                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ Bedrock   │  │ Model     │  │ Output    │               │
│  │ Guardrails│  │ Access    │  │ Filtering │               │
│  │           │  │ Controls  │  │           │               │
│  └───────────┘  └───────────┘  └───────────┘               │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                 AUDIT & COMPLIANCE                           │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │
│  │CloudTrail │  │AWS Config │  │ Security  │  │  Audit   │ │
│  │ (API Log) │  │(Compliance│  │    Hub    │  │ Manager  │ │
│  │           │  │  Rules)   │  │           │  │  (GxP)   │ │
│  └───────────┘  └───────────┘  └───────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**GxP Compliance (21 CFR Part 11):**
- ✅ Electronic signatures via IAM Identity Center
- ✅ Audit trails via CloudTrail (immutable)
- ✅ Access controls via Lake Formation
- ✅ Data integrity via S3 Object Lock
- ✅ AI governance via Bedrock Guardrails
- ✅ Pre-built controls via AWS Audit Manager

*Speaker Notes:*
Security and compliance are non-negotiable in pharma. Our architecture addresses this at four layers. Identity and access management through IAM Identity Center with attribute-based access control. Data protection through KMS encryption with separate keys per CMO, S3 Object Lock for immutability, and Macie for PII detection. AI/ML governance through Bedrock Guardrails to control model behavior and filter outputs. Audit and compliance through CloudTrail logging, Config rules, and Audit Manager with pre-built GxP frameworks. This architecture supports 21 CFR Part 11 requirements out of the box.

---

## Slide 25: Implementation Roadmap

**Title:** Phased Implementation Approach

**Visual:** Timeline with phases

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1              PHASE 2              PHASE 3              PHASE 4     │
│  Foundation           Expansion            Scale & AI           Industry    │
│  (Weeks 1-6)          (Weeks 7-12)         (Weeks 13-20)        (Ongoing)   │
│                                                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌───────────┐ │
│  │• Core infra │     │• Add Pattern│     │• Pattern 5  │     │• Extend to│ │
│  │• Pattern 4  │     │  1 & 3      │     │  (Full AI)  │     │  CROs,    │ │
│  │  (Transfer) │     │• Self-svc   │     │• Bedrock    │     │  Logistics│ │
│  │• Basic doc  │     │  portal     │     │  Knowledge  │     │• Publish  │ │
│  │  processing │     │• 5-10 CMOs  │     │  Base       │     │  ref arch │ │
│  │• 1-2 pilot  │     │• Textract   │     │• Pattern 2  │     │• Cont.    │ │
│  │  CMOs       │     │  templates  │     │  (Clean Rm) │     │  improve  │ │
│  │• Legal      │     │• Image      │     │• Cross-CMO  │     │           │ │
│  │  templates  │     │  analysis   │     │  analytics  │     │           │ │
│  └─────────────┘     └─────────────┘     └─────────────┘     └───────────┘ │
│        │                   │                   │                   │        │
│        ▼                   ▼                   ▼                   ▼        │
│   ┌─────────┐         ┌─────────┐         ┌─────────┐         ┌─────────┐  │
│   │2 CMOs   │         │10 CMOs  │         │20+ CMOs │         │Industry │  │
│   │Structured│        │+Unstruct│         │Full AI  │         │platform │  │
│   │+ Basic  │         │  Data   │         │Enabled  │         │         │  │
│   │  Docs   │         │         │         │         │         │         │  │
│   └─────────┘         └─────────┘         └─────────┘         └─────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

*Speaker Notes:*
We recommend a phased approach. Phase 1 focuses on foundation—deploying core infrastructure, implementing Pattern 4 as the universal fallback, and basic document processing with Textract. We onboard 1-2 pilot CMOs to validate the approach. Phase 2 expands to add Patterns 1 and 3, builds the self-service portal, and scales document and image processing. Phase 3 enables full AI capabilities—Bedrock knowledge base for generative AI, Clean Rooms for privacy-sensitive collaborations, and cross-CMO analytics. Phase 4 extends the platform to other partners and positions this as an industry reference architecture.

---

## Slide 26: Success Metrics

**Title:** Measuring Success

**Visual:** Metrics table with before/after

| Metric | Current State | Target State | Improvement |
|--------|---------------|--------------|-------------|
| Time to first data exchange | 3-6 months | < 2 weeks | **90%+ reduction** |
| Merck onboarding effort | 200+ hours | < 20 hours | **90% reduction** |
| CMO onboarding effort | 100+ hours | < 10 hours | **90% reduction** |
| Integration patterns | Custom each time | 5 standardized | **Repeatable** |
| Legal negotiation time | 4-8 weeks | < 1 week | **75%+ reduction** |
| Data quality issues | Manual discovery | Automated detection | **Proactive** |
| Document processing | Manual review | AI-automated | **80%+ automation** |
| Time to find information | Hours (manual search) | Seconds (Gen AI) | **99% reduction** |

**Business Outcomes:**
- 🎯 Faster access to manufacturing insights
- 🎯 Reduced integration costs
- 🎯 Scalable CMO ecosystem
- 🎯 Improved supply chain visibility
- 🎯 AI-powered quality intelligence

*Speaker Notes:*
Here's how we'll measure success. The headline metric is time-to-first-data-exchange—from 3-6 months to under 2 weeks. We'll also track effort reduction on both sides—Merck and CMO. For unstructured data, we target 80%+ automation in document processing—meaning most batch records and CoAs are processed without manual intervention. And with generative AI, finding information drops from hours of manual searching to seconds of conversation. These metrics directly translate to business outcomes: faster insights, lower costs, and AI-powered quality intelligence.

---

## Slide 27: Investment Summary

**Title:** Investment Overview

**Visual:** Cost breakdown (placeholder - actual numbers TBD)

```
┌─────────────────────────────────────────────────────────────┐
│                 IMPLEMENTATION INVESTMENT                    │
│                                                              │
│  Phase 1 (Foundation)         $XXX,XXX                      │
│  ├─ Infrastructure setup                                     │
│  ├─ Pattern 4 implementation                                 │
│  ├─ Basic Textract integration                               │
│  ├─ Pilot CMO onboarding                                    │
│  └─ Legal template development                               │
│                                                              │
│  Phase 2 (Expansion)          $XXX,XXX                      │
│  ├─ Additional patterns (1, 3)                               │
│  ├─ Self-service portal                                      │
│  ├─ Rekognition image analysis                               │
│  └─ CMO scaling                                              │
│                                                              │
│  Phase 3 (Scale & AI)         $XXX,XXX                      │
│  ├─ Bedrock knowledge base                                   │
│  ├─ Clean Rooms implementation                               │
│  ├─ Advanced analytics                                       │
│  └─ Operational handoff                                      │
│                                                              │
│  ─────────────────────────────────────────                  │
│  TOTAL IMPLEMENTATION         $X.XM                         │
│                                                              │
│  ONGOING (Monthly)            $XX,XXX                       │
│  ├─ AWS infrastructure                                       │
│  ├─ AI/ML services (Textract, Rekognition, Bedrock)         │
│  ├─ Managed services                                         │
│  └─ Support & maintenance                                    │
└─────────────────────────────────────────────────────────────┘
```

**ROI Considerations:**
- Current cost per CMO integration: $XXX,XXX
- Projected cost per CMO (with platform): $XX,XXX
- Break-even: X CMOs
- Additional value: AI insights not previously possible

*Speaker Notes:*
This slide shows the investment overview. I've left the numbers as placeholders—we'll work with you to refine these based on scope and timeline. The key ROI story is that the platform investment pays for itself after just a few CMO integrations. Each CMO you add after that is incremental cost versus the current model of custom integration every time. Additionally, the AI capabilities provide value that wasn't previously possible—automated document processing and generative AI insights represent net-new capabilities, not just cost savings.

---

## Slide 28: Why AWS

**Title:** Why AWS for Pharma Data Exchange

**Visual:** Differentiators

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. PURPOSE-BUILT SERVICES                            │   │
│  │    • AWS Data Exchange - managed data marketplace    │   │
│  │    • AWS Clean Rooms - privacy-preserving analytics  │   │
│  │    • AWS Transfer Family - managed file transfer     │   │
│  │    • Amazon Textract - intelligent document processing│  │
│  │    • Amazon Bedrock - enterprise generative AI       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2. LIFE SCIENCES EXPERTISE                           │   │
│  │    • GxP-qualified workloads                         │   │
│  │    • 21 CFR Part 11 compliance frameworks            │   │
│  │    • Pharma customer references                      │   │
│  │    • Healthcare & Life Sciences competency partners  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 3. AI/ML LEADERSHIP                                  │   │
│  │    • Broadest selection of foundation models         │   │
│  │    • Bedrock Guardrails for responsible AI           │   │
│  │    • Integrated AI services (Textract, Rekognition)  │   │
│  │    • RAG architecture for enterprise knowledge       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 4. ECOSYSTEM & SECURITY                              │   │
│  │    • CMOs already on AWS or AWS-compatible           │   │
│  │    • Snowflake partnership (runs on AWS)             │   │
│  │    • FedRAMP, HIPAA, SOC certifications              │   │
│  │    • Encryption and access control at every layer    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

*Speaker Notes:*
Why AWS for this solution? Four reasons. First, purpose-built services—Data Exchange, Clean Rooms, Transfer Family, Textract, and Bedrock are designed exactly for this use case. Second, Life Sciences expertise—we have GxP-qualified workloads and compliance frameworks ready to go. Third, AI/ML leadership—Bedrock gives you access to the best foundation models with enterprise guardrails, and integrated AI services like Textract and Rekognition are production-ready. Fourth, ecosystem and security—many CMOs are already on AWS, and we have the certifications pharma requires.

---

## Slide 29: Next Steps

**Title:** Recommended Next Steps

**Visual:** Action items with owners

```
┌─────────────────────────────────────────────────────────────┐
│                     NEXT STEPS                               │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. VALIDATE CMO PERSONAS                    Week 1-2 │   │
│  │    • Interview 3-5 CMOs on integration preferences   │   │
│  │    • Identify unstructured data types in scope       │   │
│  │    • Confirm pattern applicability                   │   │
│  │    Owner: Merck Supply Chain + AWS                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2. LEGAL TEMPLATE DEVELOPMENT               Week 2-4 │   │
│  │    • Engage Merck Legal for template creation        │   │
│  │    • Include AI/ML processing consent clauses        │   │
│  │    • Define acceptable terms for CMO agreements      │   │
│  │    Owner: Merck Legal + Procurement                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 3. PILOT CMO SELECTION                      Week 2-3 │   │
│  │    • Identify 2 CMOs (1 cloud-native, 1 legacy)     │   │
│  │    • Ensure mix of structured + unstructured data   │   │
│  │    • Secure commitment for pilot participation       │   │
│  │    Owner: Merck Supply Chain                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 4. AI USE CASE PRIORITIZATION               Week 3-4 │   │
│  │    • Identify highest-value Gen AI use cases         │   │
│  │    • Define document types for Textract templates    │   │
│  │    • Scope Bedrock knowledge base requirements       │   │
│  │    Owner: Merck Quality + AWS AI/ML Team             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 5. AWS ENGAGEMENT                           Week 4-5 │   │
│  │    • Finalize scope and SOW                          │   │
│  │    • Engage AWS ProServe or Partner                  │   │
│  │    Owner: AWS Account Team                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

*Speaker Notes:*
Here are our recommended next steps. First, validate our assumptions by interviewing 3-5 CMOs about their integration preferences and unstructured data types. Second, engage Merck Legal to develop the template library—including AI/ML processing consent. Third, select two pilot CMOs with a mix of data types. Fourth—and this is new—prioritize AI use cases with your quality team to ensure we focus Bedrock and Textract on the highest-value scenarios. Fifth, finalize the AWS engagement model. We can have Phase 1 underway within 5-6 weeks of kickoff.

---

## Slide 30: Q&A

**Title:** Questions & Discussion

**Visual:** Clean slide with contact information

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│                                                              │
│                    QUESTIONS?                                │
│                                                              │
│                                                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                      │   │
│  │  [Your Name]                                         │   │
│  │  Solutions Architect, AWS                            │   │
│  │  [email]                                             │   │
│  │                                                      │   │
│  │  AWS Life Sciences Team                              │   │
│  │  [team email/contact]                                │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

*Speaker Notes:*
Thank you for your time today. I'm happy to take any questions about the architecture, AI capabilities, implementation approach, or next steps. We're excited about the opportunity to help Merck transform CMO data integration—not just for structured data, but for the full spectrum of documents, images, and sensor data that CMOs produce.

---

## Slide 31: Appendix - AWS Services Reference (UPDATED)

**Title:** Appendix: AWS Services Used

**Data Integration Services:**
| Service | Purpose |
|---------|---------|
| AWS Data Exchange | Managed data marketplace for CMO data publishing |
| AWS Clean Rooms | Privacy-preserving collaborative analytics |
| AWS Transfer Family | Managed SFTP/FTPS for file transfer |
| Amazon S3 | Data lake storage (structured + unstructured) |
| AWS Glue | ETL, data catalog, data quality |
| AWS Lake Formation | Fine-grained access control and governance |

**AI/ML Services:**
| Service | Purpose |
|---------|---------|
| Amazon Textract | Document OCR, table/form extraction |
| Amazon Rekognition | Image analysis, defect detection |
| Amazon Comprehend | Natural language processing, entity extraction |
| Amazon Bedrock | Generative AI, knowledge base, RAG |
| Amazon Transcribe | Audio transcription (if needed) |

**IoT & Time-Series:**
| Service | Purpose |
|---------|---------|
| AWS IoT Core | Device connectivity, message routing |
| Amazon Timestream | Time-series database for sensor data |
| Amazon Managed Grafana | Real-time dashboards |

**Analytics & Search:**
| Service | Purpose |
|---------|---------|
| Amazon Athena | Serverless SQL queries |
| Amazon Redshift | Data warehouse for analytics |
| Amazon OpenSearch | Full-text search, vector store for RAG |
| Amazon QuickSight | Business intelligence dashboards |

**Security & Compliance:**
| Service | Purpose |
|---------|---------|
| AWS KMS | Encryption key management |
| Amazon Macie | Sensitive data discovery |
| AWS CloudTrail | API audit logging |
| AWS Config | Compliance monitoring |
| AWS Audit Manager | GxP compliance frameworks |

**Infrastructure:**
| Service | Purpose |
|---------|---------|
| Amazon Cognito | CMO identity management |
| AWS Amplify | Self-service portal frontend |
| Amazon API Gateway | API management |
| AWS Step Functions | Workflow orchestration |
| Amazon EventBridge | Event-driven automation |
| AWS Direct Connect | Secure network connectivity |

---

## Slide 32: Appendix - Pattern Comparison (UPDATED)

**Title:** Appendix: Detailed Pattern Comparison

| Criteria | Pattern 1 | Pattern 2 | Pattern 3 | Pattern 4 | Pattern 5 |
|----------|-----------|-----------|-----------|-----------|-----------|
| **Name** | Data Exchange | Clean Rooms | Snowflake | Transfer | Unstructured |
| **Data Type** | Structured | Structured | Structured | Both | Unstructured |
| **CMO Requirement** | AWS Account | AWS Account | Snowflake | None | None |
| **Data Movement** | Full copy | No movement | Zero-copy/S3 | File transfer | File transfer |
| **Privacy Level** | Standard | Maximum | Standard | Standard | Standard |
| **Real-time** | Near real-time | Query-based | Near real-time | Batch | Batch/Stream |
| **AI Processing** | Add Pattern 5 | Add Pattern 5 | Add Pattern 5 | Included | Native |
| **CMO Effort** | Medium | Medium | Low | Low | Low |
| **Merck Effort** | Low | Medium | Low | Medium | Low |
| **Best For** | Cloud-native | Privacy-sensitive | Snowflake users | Legacy | Docs/Images/IoT |
| **Time to Value** | 1-2 weeks | 2-3 weeks | 1-2 weeks | 2-4 weeks | 2-4 weeks |

---

## Slide 33: Appendix - Unstructured Data Types Detail

**Title:** Appendix: Unstructured Data Types & Processing

| Data Type | Examples | AWS Service | Output |
|-----------|----------|-------------|--------|
| **PDF Documents** | Batch records, CoAs, SOPs | Textract | Structured JSON |
| **Scanned Forms** | Paper records, checklists | Textract | Key-value pairs |
| **Images** | Visual inspection, labels | Rekognition | Classifications, bounding boxes |
| **Text Files** | Logs, reports, emails | Comprehend | Entities, sentiment, key phrases |
| **Audio** | Training recordings | Transcribe | Text transcripts |
| **IoT Streams** | Sensor data | IoT Core + Timestream | Time-series metrics |
| **Lab Files** | Chromatography, spectral | Custom Lambda | Parsed data |
| **All Above** | Combined knowledge | Bedrock | Natural language answers |

---

This completes the updated presentation with all unstructured data slides integrated. The presentation now covers:

1. **Slides 1-6:** Introduction and problem framing
2. **Slides 7-8:** Data types supported (NEW) and pattern overview
3. **Slides 9-12:** Patterns 1-4 (structured data)
4. **Slides 13-18:** Pattern 5 and AI capabilities (NEW)
5. **Slides 19-24:** Control plane, accelerators, security
6. **Slides 25-29:** Roadmap, metrics, investment, next steps
7. **Slides 30-33:** Q&A and appendix

Would you like me to:
1. **Create executive summary slides** for a shorter version?
2. **Develop a technical deep-dive appendix** for architects?
3. **Add customer reference examples** or case studies?
4. **Create a one-page handout** summarizing the solution?