# Pharma Data Exchange Hub - Architecture Diagram
# Requires Python 3.8+ and diagrams library
# Install: pip install diagrams
# Run: python architecture-diagram-code.py

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

with Diagram("Pharma Data Exchange Hub - CMO Integration", show=False, direction="TB"):
    
    # CMO Ecosystem
    with Cluster("CMO Ecosystem"):
        with Cluster("CMO A\nCloud Native"):
            cmo_a = GenericDatabase("Snowflake/\nDatabricks")
        
        with Cluster("CMO B\nEnterprise DB"):
            cmo_b = RDS("Oracle/\nSQL Server")
        
        with Cluster("CMO C\nLegacy"):
            cmo_c = GenericOfficeBuilding("On-Prem\nSFTP")
        
        with Cluster("CMO D\nDocuments"):
            cmo_d = Multimedia("PDFs/\nImages")
    
    # AWS Integration Hub
    with Cluster("AWS Integration Hub"):
        
        # Self-Service Onboarding
        with Cluster("Self-Service Onboarding"):
            portal = Amplify("CMO\nOnboarding\nPortal")
            api_gw = APIGateway("API\nGateway")
            portal_lambda = Lambda("Portal\nLogic")
            
            portal >> api_gw >> portal_lambda
        
        # Data Contracts & Schema Registry
        with Cluster("Data Contracts & Schema"):
            schema_registry = Glue("Glue Schema\nRegistry")
            contracts_db = Dynamodb("Data\nContracts")
            secrets = SecretsManager("CMO\nCredentials")
            
            portal_lambda >> schema_registry
            portal_lambda >> contracts_db
            portal_lambda >> secrets
        
        # Ingestion Layer - 3 Patterns
        with Cluster("Ingestion Layer"):
            with Cluster("Pattern 1\nNative Connectors"):
                glue_conn = Glue("Glue\nConnectors")
            
            with Cluster("Pattern 2\nSecure Transfer"):
                transfer_family = TransferForSftp("Transfer\nFamily\nSFTP")
            
            with Cluster("Pattern 3\nUnstructured AI"):
                textract = Textract("Textract")
                rekognition = Rekognition("Rekognition")
        
        # Data Lake - Medallion Architecture
        with Cluster("Data Lake (S3)"):
            bronze = S3("Bronze\nRaw Data")
            silver = S3("Silver\nValidated")
            gold = S3("Gold\nAggregated")
            
            bronze >> Edge(label="Glue ETL\nValidation") >> silver
            silver >> Edge(label="Glue ETL\nAggregation") >> gold
        
        # Processing & Analytics
        with Cluster("Processing & Analytics"):
            glue_etl = Glue("Glue ETL\nJobs")
            athena = Athena("Athena\nSQL")
            bedrock = Bedrock("Bedrock\nGen AI")
            
            bronze >> glue_etl >> silver
            silver >> athena
            gold >> athena
            silver >> bedrock
            gold >> bedrock
        
        # Governance & Security
        with Cluster("Governance & Security"):
            lake_formation = LakeFormation("Lake\nFormation")
            kms = KMS("KMS\nEncryption")
            cloudtrail = Cloudtrail("CloudTrail\nAudit")
            
            lake_formation >> silver
            lake_formation >> gold
            kms >> bronze
            kms >> silver
            kms >> gold
        
        # Monitoring & Orchestration
        with Cluster("Monitoring & Orchestration"):
            cloudwatch = Cloudwatch("CloudWatch")
            eventbridge = Eventbridge("EventBridge")
            step_functions = StepFunctions("Step\nFunctions")
            
            glue_etl >> cloudwatch
            cloudwatch >> eventbridge
            portal_lambda >> Edge(label="Activate") >> step_functions
            step_functions >> glue_conn
            step_functions >> transfer_family
    
    # Merck Enterprise Systems
    with Cluster("Merck Enterprise Systems"):
        erp = GenericDatabase("ERP\n(SAP)")
        qms = GenericDatabase("QMS\n(Veeva)")
        lims = GenericDatabase("LIMS")
        dw = Redshift("Data\nWarehouse")
        bi = Quicksight("QuickSight\nDashboards")
        
        athena >> Edge(label="API") >> erp
        athena >> Edge(label="API") >> qms
        athena >> Edge(label="API") >> lims
        gold >> dw
        dw >> bi
        bedrock >> bi
    
    # Data Flow Connections
    cmo_a >> glue_conn >> bronze
    cmo_b >> glue_conn >> bronze
    cmo_c >> transfer_family >> bronze
    cmo_d >> textract >> bronze
    cmo_d >> rekognition >> bronze
