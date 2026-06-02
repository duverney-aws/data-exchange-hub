# Implementation Plan: Pharma Data Exchange Hub

## Overview

This implementation plan breaks down the Pharma Data Exchange Hub into discrete, incremental tasks. The approach follows a layered implementation strategy: infrastructure and data models first, then core backend services, followed by frontend integration, and finally AI/analytics features. Each task builds on previous work to ensure continuous integration and validation.

## Tasks

- [x] 1. Set up project infrastructure and core data models
  - Create AWS CDK project structure for infrastructure as code
  - Define DynamoDB table schemas (cmo-profiles, data-contracts, pipeline-executions)
  - Set up S3 bucket structure (bronze/silver/gold layers with CMO partitioning)
  - Configure AWS Secrets Manager for credential storage
  - Set up CloudWatch log groups and metric namespaces
  - _Requirements: 1.3, 2.4, 9.1, 9.2, 14.3_

- [x] 1.1 Write property test for DynamoDB table operations

  - **Property 7: Contract ID Format Compliance**
  - **Validates: Requirements 2.4**

- [x] 1.2 Write unit tests for S3 path generation

  - Test Bronze/Silver/Gold path formatting
  - Test CMO-specific partitioning
  - _Requirements: 4.6, 9.1, 9.2_


- [x] 2. Implement Schema Registry Service
  - [x] 2.1 Create Lambda function for schema registration with AWS Glue Schema Registry
    - Implement register_schema() method supporting AVRO and JSON Schema formats
    - Implement get_schema() method with version support
    - Integrate with AWS Glue Schema Registry API
    - _Requirements: 2.2, 2.3_

  - [ ]* 2.2 Write property test for schema validation
    - **Property 5: Schema Format Validation**
    - **Validates: Requirements 2.2**

  - [x] 2.3 Implement schema compatibility checking
    - Implement validate_compatibility() method
    - Support backward, forward, and full compatibility modes
    - _Requirements: 2.7_

  - [ ]* 2.4 Write property test for schema compatibility
    - **Property 10: Schema Compatibility Checking**
    - **Validates: Requirements 2.7**

  - [x] 2.4 Implement schema inference from sample data
    - Support CSV, JSON, and Parquet file formats
    - Infer field names, types, and basic constraints
    - Implement schema merging for multiple files
    - _Requirements: 3.1, 3.5_

  - [ ]* 2.5 Write property test for schema inference
    - **Property 11: Schema Inference from Sample Data**
    - **Validates: Requirements 3.1**

  - [ ]* 2.6 Write property test for schema merging
    - **Property 12: Schema Merging from Multiple Files**
    - **Validates: Requirements 3.5**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Data Contract Management API
  - [x] 4.1 Create API Gateway REST API with Lambda handlers
    - POST /api/contract - Create data contract
    - PUT /api/contract/{contractId} - Update data contract
    - GET /api/contract/{contractId} - Get contract details
    - POST /api/contract/{contractId}/activate - Activate pipeline
    - _Requirements: 2.1, 4.1_

  - [x] 4.2 Implement contract validation logic
    - Validate all required components (schema, quality rules, SLAs, delivery, governance)
    - Validate quality rules are executable DQDL
    - Validate SLA thresholds are measurable
    - Generate unique contract IDs in format CMO-{NAME}-{DOMAIN}-{NUMBER}
    - _Requirements: 2.1, 2.4, 2.5, 2.6_

  - [ ]* 4.3 Write property test for contract component capture
    - **Property 4: Data Contract Component Capture**
    - **Validates: Requirements 2.1**

  - [ ]* 4.4 Write property test for quality rule validation
    - **Property 8: Quality Rule Executability**
    - **Validates: Requirements 2.5**

  - [ ]* 4.5 Write property test for SLA validation
    - **Property 9: SLA Threshold Measurability**
    - **Validates: Requirements 2.6**

  - [x] 4.6 Implement DynamoDB operations for contracts
    - Save contracts to data-contracts table
    - Query contracts by CMO ID
    - Update contract status
    - _Requirements: 2.4_

  - [ ]* 4.7 Write unit tests for DynamoDB operations
    - Test contract creation and retrieval
    - Test contract updates
    - Test query by CMO ID
    - _Requirements: 2.4_


- [x] 5. Implement Pipeline Orchestration with Step Functions
  - [x] 5.1 Create Step Functions state machine for pipeline deployment
    - Define workflow states (ValidateContract, DeterminePattern, ConfigurePattern, CreateETLJob, etc.)
    - Implement Lambda functions for each workflow task
    - Configure retry logic with exponential backoff (3 attempts)
    - _Requirements: 4.1, 4.2, 15.1_

  - [ ]* 5.2 Write property test for workflow triggering
    - **Property 13: Pipeline Deployment Workflow Triggering**
    - **Validates: Requirements 4.1**

  - [x] 5.3 Implement pattern-specific configuration tasks
    - ConfigureGlueConnector for Pattern 1 (native connectors)
    - ProvisionSFTP for Pattern 2 (secure transfer)
    - ConfigureAIProcessing for Pattern 3 (AI unstructured)
    - _Requirements: 4.3, 4.4, 4.5_

  - [x] 5.4 Implement ETL job creation and S3 path configuration
    - Generate Glue ETL job definitions from contracts
    - Configure S3 paths following pattern: s3://bucket/{layer}/{cmo-id}/{data-domain}/
    - Register jobs with AWS Glue
    - _Requirements: 4.2, 4.6_

  - [ ]* 5.5 Write property test for S3 path pattern
    - **Property 14: S3 Path Pattern Compliance**
    - **Validates: Requirements 4.6**

  - [x] 5.6 Implement deployment error handling and notifications
    - Log errors to CloudWatch
    - Send SNS notifications on failure
    - Provide actionable error messages
    - _Requirements: 4.8, 15.2_

  - [ ]* 5.7 Write property test for retry logic
    - **Property 34: Pipeline Retry with Exponential Backoff**
    - **Validates: Requirements 15.1, 15.2**

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement Pattern 1: Native Database Connectors
  - [x] 7.1 Create Glue connector configurations for supported platforms
    - Snowflake native connector
    - JDBC connectors for Oracle, SQL Server, PostgreSQL, SAP
    - Databricks native connector
    - _Requirements: 5.1_

  - [ ]* 7.2 Write property test for connection type support
    - **Property 15: Connection Type Support**
    - **Validates: Requirements 5.1**

  - [x] 7.3 Implement connectivity testing
    - Test database connections before pipeline activation
    - Return success/failure status with error details
    - _Requirements: 5.2_

  - [ ]* 7.4 Write property test for connectivity testing
    - **Property 16: Connectivity Testing Before Activation**
    - **Validates: Requirements 5.2**

  - [x] 7.4 Implement data extraction to Bronze layer
    - Extract data using JDBC or native APIs
    - Write to Bronze in Parquet format with Snappy compression
    - Apply date partitioning (year/month/day)
    - Log row counts and execution time to CloudWatch
    - _Requirements: 5.3, 5.4, 5.5_

  - [ ]* 7.5 Write property test for Bronze layer writing
    - **Property 17: Data Writing to Bronze Layer**
    - **Validates: Requirements 5.4, 9.1, 9.2, 9.6**


- [-] 8. Implement Pattern 2: Secure File Transfer (SFTP)
  - [x] 8.1 Create Lambda function to provision AWS Transfer Family SFTP endpoints
    - Generate unique SFTP credentials per CMO
    - Store credentials in AWS Secrets Manager
    - Configure S3 home directory for CMO
    - Return hostname, username, and password
    - _Requirements: 6.1, 6.2_

  - [ ]* 8.2 Write property test for unique credential generation
    - **Property 2: Unique Credential Generation**
    - **Validates: Requirements 1.3, 6.2**

  - [x] 8.3 Implement S3 event-driven file processing
    - Configure S3 event notifications for new file uploads
    - Create Lambda function to detect and process files
    - Validate file format against contract schema
    - Move validated files to Bronze layer with date partitioning
    - Archive original files
    - _Requirements: 6.3, 6.4, 6.5, 6.6_

  - [ ]* 8.4 Write property test for file format validation
    - **Property 18: File Format Validation Against Schema**
    - **Validates: Requirements 6.4**

  - [ ]* 8.5 Write unit tests for file processing
    - Test file detection via S3 events
    - Test file archival
    - Test error handling for invalid files
    - _Requirements: 6.3, 6.6_

- [x] 9. Implement Pattern 3: AI-Powered Unstructured Data Processing
  - [x] 9.1 Create Lambda function for document processing with Amazon Textract
    - Detect document type (PDF, image)
    - Extract text, tables, and forms using Textract
    - Parse extraction results into JSON matching contract schema
    - Calculate extraction confidence scores
    - _Requirements: 7.1, 7.2_

  - [x] 9.2 Create Lambda function for image processing with Amazon Rekognition
    - Detect defects, labels, and text in images
    - Parse detection results into JSON
    - Calculate detection confidence scores
    - _Requirements: 7.3_

  - [x] 9.3 Implement confidence thresholding and manual review flagging
    - Flag records with confidence < 85% for manual review
    - Write high-confidence records to Bronze layer
    - Store flagged records in separate S3 prefix
    - _Requirements: 7.5, 7.6_

  - [ ]* 9.4 Write property test for confidence thresholding
    - **Property 19: AI Extraction Confidence Thresholding**
    - **Validates: Requirements 7.5**

  - [ ]* 9.5 Write unit tests for AI processing
    - Test Textract extraction with sample PDFs
    - Test Rekognition detection with sample images
    - Test JSON parsing and schema compliance
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 11. Implement ETL Processing and Data Quality Validation
  - [x] 11.1 Create Glue ETL job template for Bronze to Silver transformation
    - Read data from Bronze layer
    - Validate against registered schema
    - Apply data type conversions and null handling
    - Implement deduplication logic
    - _Requirements: 8.1, 9.3_

  - [x] 11.2 Implement AWS Glue Data Quality validation
    - Build DQDL rulesets from contract quality rules
    - Check completeness, accuracy, uniqueness, and consistency
    - Generate quality metrics and reports
    - _Requirements: 8.2_

  - [ ]* 11.3 Write property test for comprehensive validation
    - **Property 20: Comprehensive Data Quality Validation**
    - **Validates: Requirements 8.1, 8.2**

  - [x] 11.4 Implement validation pass/fail handling
    - Promote passing data to Silver layer with validation timestamp
    - Quarantine failed records in separate S3 prefix with contract ID and timestamp
    - Register Silver tables in Glue Data Catalog
    - _Requirements: 8.3, 8.4, 9.4_

  - [ ]* 11.5 Write property test for validation pass promotion
    - **Property 21: Validation Pass Promotes to Silver**
    - **Validates: Requirements 8.3, 9.3, 9.4**

  - [ ]* 11.6 Write property test for validation failure quarantine
    - **Property 22: Validation Failure Quarantines Data**
    - **Validates: Requirements 8.4**

  - [x] 11.7 Implement quality metrics logging and notifications
    - Log quality scores to CloudWatch
    - Update contract status in DynamoDB
    - Send SNS notifications when thresholds are breached
    - _Requirements: 8.5, 8.6_

  - [ ]* 11.8 Write unit tests for quality metrics
    - Test CloudWatch metric publishing
    - Test DynamoDB status updates
    - Test SNS notification sending
    - _Requirements: 8.5, 8.6_

- [x] 12. Implement Gold Layer Aggregations
  - [x] 12.1 Create Glue ETL jobs for business-ready aggregations
    - Aggregate batch records by time period (daily, weekly, monthly)
    - Calculate quality metrics and trends
    - Create CMO performance summaries
    - Optimize for query performance (denormalization, pre-aggregation)
    - _Requirements: 9.5_

  - [ ]* 12.2 Write unit tests for aggregation logic
    - Test time-based aggregations
    - Test metric calculations
    - Test denormalization logic
    - _Requirements: 9.5_

- [x] 13. Implement Data Encryption and Security
  - [x] 13.1 Configure AWS KMS customer-managed keys per CMO
    - Create CMO-specific KMS keys
    - Configure S3 bucket encryption with KMS
    - Set up key rotation policies
    - _Requirements: 9.7_

  - [ ]* 13.2 Write property test for data encryption
    - **Property 23: Data Encryption with CMO-Specific Keys**
    - **Validates: Requirements 9.7**

  - [x] 13.3 Implement IAM roles with least-privilege permissions
    - Create CMO-specific IAM roles
    - Limit permissions to required resources and actions
    - Configure trust relationships
    - _Requirements: 10.1_

  - [ ]* 13.4 Write property test for IAM role permissions
    - **Property 24: IAM Role Least Privilege**
    - **Validates: Requirements 10.1**

- [x] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 15. Implement Access Control with AWS Lake Formation
  - [x] 15.1 Configure Lake Formation for Glue Data Catalog
    - Register S3 locations with Lake Formation
    - Configure database and table permissions
    - Set up data filters for row-level and column-level security
    - _Requirements: 10.2_

  - [x] 15.2 Implement CMO data isolation
    - Create row filters: WHERE cmo_id = '{cmo_id}'
    - Grant permissions based on user-CMO associations
    - Test cross-CMO access prevention
    - _Requirements: 10.2, 10.3_

  - [ ]* 15.3 Write property test for access control enforcement
    - **Property 25: Lake Formation Access Control Enforcement**
    - **Validates: Requirements 10.2, 10.3, 13.5**

  - [x] 15.4 Implement PII detection and masking with Amazon Macie
    - Configure Macie classification jobs for Silver layer
    - Detect PII fields (names, emails, phone numbers, SSNs)
    - Apply masking rules (hashing, redaction) based on data classification
    - _Requirements: 10.4_

  - [ ]* 15.5 Write property test for PII masking
    - **Property 26: PII Detection and Masking**
    - **Validates: Requirements 10.4**

  - [ ]* 15.6 Write unit tests for access control
    - Test authorized access succeeds
    - Test unauthorized access fails
    - Test row-level filtering
    - Test column-level filtering
    - _Requirements: 10.2, 10.3_

- [x] 16. Implement Audit Logging and Compliance
  - [x] 16.1 Configure AWS CloudTrail for comprehensive logging
    - Enable CloudTrail for all API calls
    - Log data access events via Lake Formation
    - Configure S3 bucket with object lock for immutability
    - Set retention policy to 7 years
    - _Requirements: 10.5, 14.1, 14.2, 14.3, 14.5_

  - [ ]* 16.2 Write property test for audit logging
    - **Property 27: Comprehensive Audit Logging**
    - **Validates: Requirements 10.5, 14.1, 14.2**

  - [ ]* 16.3 Write property test for log encryption and immutability
    - **Property 33: Audit Log Encryption and Immutability**
    - **Validates: Requirements 14.3, 14.5**

  - [x] 16.4 Implement audit report generation
    - Create Lambda function to query CloudTrail logs
    - Generate compliance reports (user actions, data access, modifications)
    - Export reports in PDF format
    - _Requirements: 14.4_

  - [x] 16.5 Implement electronic signature capture
    - Capture user authentication details
    - Record user intent for critical actions
    - Store signatures with audit trail
    - _Requirements: 14.6_

  - [ ]* 16.6 Write unit tests for audit reporting
    - Test report generation from CloudTrail logs
    - Test report formatting
    - Test electronic signature capture
    - _Requirements: 14.4, 14.6_


- [x] 17. Implement SLA Monitoring and Alerting
  - [x] 17.1 Create CloudWatch custom metrics for pipeline execution
    - Record execution time, record counts, quality scores
    - Publish metrics with CMO and contract dimensions
    - _Requirements: 11.1, 11.2_

  - [x] 17.2 Implement SLA compliance checking
    - Compare execution time against SLA timeliness thresholds
    - Compare quality scores against SLA quality thresholds
    - Track availability (success rate, uptime percentage)
    - _Requirements: 11.1, 11.2, 11.5_

  - [ ]* 17.3 Write property test for SLA monitoring and alerting
    - **Property 28: SLA Compliance Monitoring and Alerting**
    - **Validates: Requirements 11.1, 11.2, 11.3**

  - [x] 17.4 Create CloudWatch dashboards for SLA compliance
    - Display compliance trends per CMO
    - Show execution time, quality scores, availability metrics
    - Visualize SLA threshold breaches
    - _Requirements: 11.4_

  - [x] 17.5 Configure CloudWatch alarms for SLA violations
    - Create alarms with severity levels (warning, critical)
    - Send SNS notifications to operations team
    - Configure alarm actions (auto-scaling, incident creation)
    - _Requirements: 11.3, 11.6_

  - [ ]* 17.6 Write unit tests for monitoring
    - Test metric publishing
    - Test SLA threshold comparison
    - Test alarm triggering
    - _Requirements: 11.1, 11.2, 11.3, 11.6_

- [x] 18. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19. Implement Natural Language Query Service with Amazon Bedrock
  - [x] 19.1 Create Lambda function for natural language query processing
    - Integrate with Amazon Bedrock (Claude 3)
    - Get user's accessible tables from Lake Formation
    - Build schema context from Glue Data Catalog
    - _Requirements: 12.1_

  - [x] 19.2 Implement SQL generation from natural language
    - Send user query and schema context to Bedrock
    - Parse SQL from Bedrock response
    - Validate generated SQL for safety (no DROP, DELETE, etc.)
    - _Requirements: 12.2_

  - [ ]* 19.3 Write property test for SQL generation
    - **Property 29: Natural Language to SQL Generation**
    - **Validates: Requirements 12.1, 12.2, 12.5**

  - [x] 19.4 Implement SQL execution with Athena
    - Execute generated SQL via Athena
    - Enforce Lake Formation access controls
    - Handle query timeouts and errors
    - _Requirements: 12.3_

  - [ ]* 19.5 Write property test for SQL execution
    - **Property 30: SQL Execution via Athena**
    - **Validates: Requirements 12.3**

  - [x] 19.6 Implement natural language response formatting
    - Send query results to Bedrock for formatting
    - Generate clear, concise natural language responses
    - Handle ambiguous queries with clarifying questions
    - _Requirements: 12.4, 12.6_

  - [ ]* 19.7 Write property test for response formatting
    - **Property 31: Natural Language Response Formatting**
    - **Validates: Requirements 12.4**

  - [ ]* 19.8 Write unit tests for NL query service
    - Test SQL generation with sample queries
    - Test access control enforcement
    - Test error handling
    - Test ambiguous query handling
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_


- [x] 20. Implement Business Intelligence with Amazon QuickSight
  - [x] 20.1 Create QuickSight data sources from Athena
    - Configure Athena connection
    - Create datasets for batch records, quality metrics, SLA compliance
    - Set up data refresh schedules based on contract delivery frequency
    - _Requirements: 13.2, 13.4_

  - [ ]* 20.2 Write property test for data refresh scheduling
    - **Property 32: QuickSight Data Refresh Scheduling**
    - **Validates: Requirements 13.4**

  - [x] 20.3 Create QuickSight dashboards
    - Batch records dashboard (volume, trends, status)
    - Quality metrics dashboard (scores, failures, trends)
    - SLA compliance dashboard (timeliness, availability, quality)
    - _Requirements: 13.1_

  - [x] 20.4 Configure row-level security in QuickSight
    - Integrate with Lake Formation permissions
    - Enforce CMO data isolation
    - Test access control with different user roles
    - _Requirements: 13.5_

  - [x] 20.5 Implement dashboard filters and interactivity
    - Add filters for CMO, date range, data domain
    - Enable drill-down capabilities
    - Configure real-time visualization updates
    - _Requirements: 13.3_

  - [ ]* 20.6 Write unit tests for QuickSight integration
    - Test data source configuration
    - Test refresh scheduling
    - Test row-level security
    - _Requirements: 13.2, 13.4, 13.5_

- [x] 21. Implement Error Handling and Recovery
  - [x] 21.1 Implement circuit breaker pattern for downstream services
    - Create CircuitBreaker class with CLOSED/OPEN/HALF_OPEN states
    - Configure failure thresholds and timeout periods
    - Apply to Glue, Athena, Bedrock service calls
    - _Requirements: 15.5_

  - [x] 21.2 Implement idempotency for pipeline operations
    - Check for existing records before insertion
    - Use unique identifiers for deduplication
    - Ensure safe retries without data duplication
    - _Requirements: 15.6_

  - [ ]* 21.3 Write property test for idempotency
    - **Property 35: Idempotent Pipeline Operations**
    - **Validates: Requirements 15.6**

  - [x] 21.4 Implement error queuing and reprocessing
    - Queue failed records for network errors
    - Implement retry mechanism with exponential backoff
    - Log detailed error messages with record identifiers
    - _Requirements: 15.3, 15.4_

  - [ ]* 21.5 Write unit tests for error handling
    - Test circuit breaker state transitions
    - Test idempotency with duplicate operations
    - Test error queuing and reprocessing
    - _Requirements: 15.3, 15.4, 15.5, 15.6_

- [x] 22. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [ ] 23. Implement Frontend Self-Service Portal with React and Cloudscape
  - [x] 23.1 Set up React project with AWS Cloudscape Design System
    - Initialize React project with TypeScript
    - Install @cloudscape-design/components and dependencies
    - Configure AWS Amplify for hosting
    - Set up routing with React Router
    - _Requirements: 16.1_

  - [x] 23.2 Create CMO registration and authentication pages
    - Registration form with organization details
    - Form validation for required fields
    - Integration with backend API (POST /api/cmo/register)
    - Display success/error messages
    - _Requirements: 1.1, 1.2_

  - [ ]* 23.3 Write property test for registration validation
    - **Property 1: CMO Registration Validation**
    - **Validates: Requirements 1.2**

  - [x] 23.4 Create data contract management pages
    - Contract creation form (schema, quality rules, SLAs, delivery, governance)
    - Contract list view with filtering and sorting
    - Contract detail view with edit capability
    - Integration with backend API (POST/PUT/GET /api/contract)
    - _Requirements: 2.1_

  - [x] 23.5 Implement integration pattern selection UI
    - Pattern selection cards (Pattern 1, 2, 3)
    - Pattern-specific configuration forms
    - Pattern 1: Connection string and credential inputs
    - Pattern 2: SFTP credential display
    - Pattern 3: Document upload interface
    - _Requirements: 1.4, 1.5, 1.6, 1.7_

  - [ ]* 23.6 Write property test for pattern-specific configuration
    - **Property 3: Pattern-Specific Configuration Display**
    - **Validates: Requirements 1.4**

  - [x] 23.7 Implement schema inference UI
    - File upload component for sample data
    - Display inferred schema with edit capability
    - Schema approval workflow
    - Manual schema definition fallback
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 23.8 Implement pipeline activation and monitoring UI
    - Pipeline activation button
    - Pipeline status display (deploying, active, failed)
    - Connection details display
    - Error message display with actionable guidance
    - _Requirements: 4.1, 4.7, 4.8_

  - [x] 23.9 Implement data tables with Cloudscape components
    - Use Cloudscape Table component
    - Implement sorting, filtering, and pagination
    - Configure column definitions
    - _Requirements: 16.5_

  - [ ]* 23.10 Write property test for table functionality
    - **Property 36: Table Sorting, Filtering, and Pagination**
    - **Validates: Requirements 16.5**

  - [x] 23.11 Implement loading indicators and user feedback
    - Display loading spinners during API calls
    - Show success flash messages for completed actions
    - Show error flash messages with actionable guidance
    - _Requirements: 16.6, 16.7_

  - [ ]* 23.12 Write property test for user feedback display
    - **Property 37: User Feedback Display**
    - **Validates: Requirements 16.6, 16.7**

  - [x] 23.13 Implement natural language query interface
    - Query input field
    - Submit button
    - Results display with formatted response
    - Loading indicator during query processing
    - _Requirements: 12.1, 12.4_

  - [ ]* 23.14 Write unit tests for frontend components
    - Test form validation
    - Test API integration
    - Test error handling
    - Test user interactions
    - _Requirements: 1.1, 1.2, 2.1, 4.1_

- [ ] 24. Integration and End-to-End Testing
  - [x] 24.1 Set up integration test environment
    - Use existing AWS account profile `hub-387776852668` for testing
    - Deploy infrastructure with CDK using the hub profile
    - Configure test data and credentials
    - _Requirements: All_

  - [x] 24.2 Implement Pattern 1 end-to-end test
    - Register CMO and create contract with Pattern 1
    - Configure Snowflake connector
    - Activate pipeline
    - Verify data extraction to Bronze
    - Verify validation and promotion to Silver
    - Verify aggregation to Gold
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 8.1, 8.2, 8.3, 9.5_

  - [x] 24.3 Implement Pattern 2 end-to-end test
    - Register CMO and create contract with Pattern 2
    - Provision SFTP endpoint
    - Upload sample CSV file
    - Verify file detection and processing
    - Verify data quality validation
    - Verify file archival
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 8.1, 8.2, 8.3_

  - [x] 24.4 Implement Pattern 3 end-to-end test
    - Register CMO and create contract with Pattern 3
    - Upload sample PDF document
    - Verify Textract extraction
    - Verify JSON parsing and schema compliance
    - Verify confidence thresholding
    - Verify manual review flagging
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2_

  - [x] 24.5 Implement natural language query end-to-end test
    - Submit natural language question
    - Verify SQL generation
    - Verify Athena execution
    - Verify access control enforcement
    - Verify natural language response
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 24.6 Implement access control end-to-end test
    - Create users with different permissions
    - Test authorized access succeeds
    - Test unauthorized access fails
    - Test CMO data isolation
    - Test row-level and column-level filtering
    - _Requirements: 10.1, 10.2, 10.3_

- [x] 25. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 26. Documentation and Deployment
  - [x] 26.1 Create deployment documentation
    - Infrastructure deployment guide (CDK commands)
    - Configuration guide (environment variables, secrets)
    - Troubleshooting guide
    - _Requirements: All_

  - [x] 26.2 Create user documentation
    - CMO onboarding guide
    - Data contract creation guide
    - Integration pattern selection guide
    - Natural language query guide
    - _Requirements: All_

  - [x] 26.3 Deploy to production environment
    - Deploy infrastructure with CDK
    - Configure production secrets and credentials
    - Run smoke tests
    - Monitor initial deployments
    - _Requirements: All_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
