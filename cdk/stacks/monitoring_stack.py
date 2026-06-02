"""
CloudWatch Monitoring Stack for Pharma Data Exchange Hub
Sets up log groups, metric namespaces, and dashboards
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
)
from constructs import Construct


class MonitoringStack(Stack):
    """Stack for CloudWatch logs, metrics, and monitoring"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Log Groups for different components
        self.api_log_group = logs.LogGroup(
            self,
            "APILogGroup",
            log_group_name="/pharma-data-exchange/api",
            retention=logs.RetentionDays.ONE_YEAR,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.pipeline_log_group = logs.LogGroup(
            self,
            "PipelineLogGroup",
            log_group_name="/pharma-data-exchange/pipeline",
            retention=logs.RetentionDays.ONE_YEAR,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.etl_log_group = logs.LogGroup(
            self,
            "ETLLogGroup",
            log_group_name="/pharma-data-exchange/etl",
            retention=logs.RetentionDays.ONE_YEAR,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.schema_registry_log_group = logs.LogGroup(
            self,
            "SchemaRegistryLogGroup",
            log_group_name="/pharma-data-exchange/schema-registry",
            retention=logs.RetentionDays.ONE_YEAR,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.ai_processing_log_group = logs.LogGroup(
            self,
            "AIProcessingLogGroup",
            log_group_name="/pharma-data-exchange/ai-processing",
            retention=logs.RetentionDays.ONE_YEAR,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # SNS Topics for alerts
        self.critical_alerts_topic = sns.Topic(
            self,
            "CriticalAlertsTopic",
            topic_name="pharma-data-exchange-critical-alerts",
            display_name="Critical Alerts for Pharma Data Exchange Hub",
        )

        self.warning_alerts_topic = sns.Topic(
            self,
            "WarningAlertsTopic",
            topic_name="pharma-data-exchange-warning-alerts",
            display_name="Warning Alerts for Pharma Data Exchange Hub",
        )

        self.sla_breach_topic = sns.Topic(
            self,
            "SLABreachTopic",
            topic_name="pharma-data-exchange-sla-breach",
            display_name="SLA Breach Notifications",
        )

        # Custom Metric Namespaces (metrics will be published at runtime)
        # Namespace: CMO/DataPipeline
        # Metrics:
        #   - ExecutionTime (Seconds) - Dimensions: ContractId, CMOId
        #   - RecordsProcessed (Count) - Dimensions: ContractId, CMOId
        #   - QualityScore (Percent) - Dimensions: ContractId, CMOId
        #   - ValidationFailures (Count) - Dimensions: ContractId, CMOId
        #   - SLACompliance (Percent) - Dimensions: ContractId, CMOId

        # Namespace: CMO/SchemaRegistry
        # Metrics:
        #   - SchemaRegistrations (Count) - Dimensions: CMOId
        #   - SchemaValidationFailures (Count) - Dimensions: CMOId
        #   - CompatibilityCheckFailures (Count) - Dimensions: CMOId

        # Namespace: CMO/AIProcessing
        # Metrics:
        #   - DocumentsProcessed (Count) - Dimensions: CMOId, DocumentType
        #   - ExtractionConfidence (Percent) - Dimensions: CMOId, DocumentType
        #   - ManualReviewRequired (Count) - Dimensions: CMOId

        # Create main dashboard
        self.main_dashboard = cloudwatch.Dashboard(
            self,
            "MainDashboard",
            dashboard_name="PharmaDataExchangeHub",
        )

        # Add widgets to dashboard (will be populated with actual metrics at runtime)
        self.main_dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="# Pharma Data Exchange Hub - Operational Dashboard\n\n"
                         "Monitor CMO data pipelines, quality metrics, and SLA compliance.",
                width=24,
                height=2,
            )
        )

        # ----- SLA Compliance Section -----
        sla_namespace = "CMO/DataPipeline"

        self.main_dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="## SLA Compliance\n\n"
                         "Execution time, quality scores, availability, and success rate per CMO.",
                width=24,
                height=2,
            )
        )

        # ExecutionTime line graph
        self.main_dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Execution Time",
                width=12,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace=sla_namespace,
                        metric_name="ExecutionTime",
                        dimensions_map={"CMOId": "ALL"},
                        statistic="Average",
                        period=Duration.minutes(5),
                    ),
                ],
            ),
            # QualityScore line graph
            cloudwatch.GraphWidget(
                title="Quality Score",
                width=12,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace=sla_namespace,
                        metric_name="QualityScore",
                        dimensions_map={"CMOId": "ALL"},
                        statistic="Average",
                        period=Duration.minutes(5),
                    ),
                ],
            ),
        )

        # AvailabilityPercent line graph + SuccessRate single value
        self.main_dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Availability Percent",
                width=12,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace=sla_namespace,
                        metric_name="AvailabilityPercent",
                        dimensions_map={"CMOId": "ALL"},
                        statistic="Average",
                        period=Duration.minutes(5),
                    ),
                ],
            ),
            cloudwatch.SingleValueWidget(
                title="Success Rate",
                width=12,
                height=6,
                metrics=[
                    cloudwatch.Metric(
                        namespace=sla_namespace,
                        metric_name="SuccessRate",
                        dimensions_map={"CMOId": "ALL"},
                        statistic="Average",
                        period=Duration.minutes(5),
                    ),
                ],
            ),
        )

        # ----- SLA Violation Alarms (Requirements 11.3, 11.6) -----
        sla_max_execution_seconds = 3600  # 1-hour SLA default

        # ExecutionTime alarms
        execution_time_metric = cloudwatch.Metric(
            namespace=sla_namespace,
            metric_name="ExecutionTime",
            dimensions_map={"CMOId": "ALL"},
            statistic="Average",
            period=Duration.minutes(5),
        )

        self.execution_time_warning_alarm = cloudwatch.Alarm(
            self,
            "ExecutionTimeWarningAlarm",
            alarm_name="SLA-ExecutionTime-Warning",
            alarm_description=(
                "ExecutionTime exceeded 80% of SLA "
                f"({sla_max_execution_seconds * 0.80:.0f}s of "
                f"{sla_max_execution_seconds}s max)"
            ),
            metric=execution_time_metric,
            threshold=sla_max_execution_seconds * 0.80,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=3,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.execution_time_warning_alarm.add_alarm_action(
            cw_actions.SnsAction(self.warning_alerts_topic)
        )

        self.execution_time_critical_alarm = cloudwatch.Alarm(
            self,
            "ExecutionTimeCriticalAlarm",
            alarm_name="SLA-ExecutionTime-Critical",
            alarm_description=(
                "ExecutionTime exceeded 100% of SLA "
                f"({sla_max_execution_seconds}s max)"
            ),
            metric=execution_time_metric,
            threshold=float(sla_max_execution_seconds),
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=3,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.execution_time_critical_alarm.add_alarm_action(
            cw_actions.SnsAction(self.critical_alerts_topic)
        )
        self.execution_time_critical_alarm.add_alarm_action(
            cw_actions.SnsAction(self.sla_breach_topic)
        )

        # QualityScore alarms
        quality_score_metric = cloudwatch.Metric(
            namespace=sla_namespace,
            metric_name="QualityScore",
            dimensions_map={"CMOId": "ALL"},
            statistic="Average",
            period=Duration.minutes(5),
        )

        self.quality_score_warning_alarm = cloudwatch.Alarm(
            self,
            "QualityScoreWarningAlarm",
            alarm_name="SLA-QualityScore-Warning",
            alarm_description="QualityScore dropped below warning threshold (95%)",
            metric=quality_score_metric,
            threshold=95.0,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=3,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.quality_score_warning_alarm.add_alarm_action(
            cw_actions.SnsAction(self.warning_alerts_topic)
        )

        self.quality_score_critical_alarm = cloudwatch.Alarm(
            self,
            "QualityScoreCriticalAlarm",
            alarm_name="SLA-QualityScore-Critical",
            alarm_description="QualityScore dropped below critical threshold (90%)",
            metric=quality_score_metric,
            threshold=90.0,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=3,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.quality_score_critical_alarm.add_alarm_action(
            cw_actions.SnsAction(self.critical_alerts_topic)
        )
        self.quality_score_critical_alarm.add_alarm_action(
            cw_actions.SnsAction(self.sla_breach_topic)
        )

        # SuccessRate alarms
        success_rate_metric = cloudwatch.Metric(
            namespace=sla_namespace,
            metric_name="SuccessRate",
            dimensions_map={"CMOId": "ALL"},
            statistic="Average",
            period=Duration.minutes(5),
        )

        self.success_rate_warning_alarm = cloudwatch.Alarm(
            self,
            "SuccessRateWarningAlarm",
            alarm_name="SLA-SuccessRate-Warning",
            alarm_description="SuccessRate dropped below warning threshold (99%)",
            metric=success_rate_metric,
            threshold=99.0,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=3,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.success_rate_warning_alarm.add_alarm_action(
            cw_actions.SnsAction(self.warning_alerts_topic)
        )

        self.success_rate_critical_alarm = cloudwatch.Alarm(
            self,
            "SuccessRateCriticalAlarm",
            alarm_name="SLA-SuccessRate-Critical",
            alarm_description="SuccessRate dropped below critical threshold (95%)",
            metric=success_rate_metric,
            threshold=95.0,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=3,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.success_rate_critical_alarm.add_alarm_action(
            cw_actions.SnsAction(self.critical_alerts_topic)
        )
        self.success_rate_critical_alarm.add_alarm_action(
            cw_actions.SnsAction(self.sla_breach_topic)
        )


