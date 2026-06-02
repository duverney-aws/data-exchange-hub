#!/usr/bin/env python3
# Pharma Data Exchange Hub - Simplified Architecture Diagram
# Requires: Python 3.8+ and diagrams library
# Install: pip install diagrams
# Run: python pharma-architecture-simple.py

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb, RDS, Redshift
from diagrams.aws.analytics import Glue, Athena, Quicksight, LakeFormation
from diagrams.aws.storage import S3
from diagrams.aws.integration import Eventbridge, StepFunctions
from diagrams.aws.security import KMS, SecretsManager, Cloudtrail
from diagrams.aws.management import Cloudwatch
from diagrams.aws.network import APIGateway
from diagrams.aws.mobile import Amplify
from diagrams.aws.ml import Textract, Rekognition, Bedrock
from diagrams.aws.migration import TransferForSftp
from diagrams.aws.general import User, GenericDatabase, GenericOfficeBuilding, Multimedia

# Main diagram
with Diagram("Pharma Data Exchange Hub", show=False, direction="LR", filename="pharma-hub-architecture"):
    
    # CMOs
    with Cluster("CMO Ecosystem"):
        cmo_cloud = GenericDatabase("CMO Cloud DW")
        cmo_db = RDS("CMO Oracle")
        cmo_legacy = GenericOfficeBuilding("CMO Legacy")
        cmo_docs = Multimedia("CMO Docs")
    
    # AWS Hub
    with Cluster("AWS Integration Hub"):
        
        # Portal
        with Cluster("Onboarding"):
            portal = Amplify("Portal")
            api = APIGateway("API")
            fn = Lambda("Functions")
        
        # Schema
        with Cluster("Schema & Contracts"):
            schema = Glue("Schema Registry")
            contracts = Dynamodb("Contracts")
        
        # Ingestion
        with Cluster("Ingestion"):
            glue_etl = Glue("Glue")
            sftp = TransferForSftp("SFTP")
            ai_text = Textract("Textract")
        
        # Data Lake
        with Cluster("Data Lake"):
            bronze = S3("Bronze")
            silver = S3("Silver")
            gold = S3("Gold")
        
        # Analytics
        athena_svc = Athena("Athena")
        bedrock_svc = Bedrock("Bedrock")
        
        # Governance
        lf = LakeFormation("Lake Formation")
        kms_svc = KMS("KMS")
    
    # Merck
    with Cluster("Merck Systems"):
        dw = Redshift("Data Warehouse")
        bi = Quicksight("QuickSight")
    
    # Flows
    portal >> api >> fn
    fn >> schema
    fn >> contracts
    
    cmo_cloud >> glue_etl
    cmo_db >> glue_etl
    cmo_legacy >> sftp
    cmo_docs >> ai_text
    
    glue_etl >> bronze
    sftp >> bronze
    ai_text >> bronze
    
    bronze >> silver >> gold
    
    lf >> silver
    lf >> gold
    kms_svc >> bronze
    
    silver >> athena_svc
    gold >> athena_svc
    silver >> bedrock_svc
    
    gold >> dw >> bi
    bedrock_svc >> bi

print("Diagram generated successfully: pharma-hub-architecture.png")
