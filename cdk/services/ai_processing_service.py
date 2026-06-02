"""
AI Processing Service

Implements Pattern 3: AI-Powered Unstructured Data Processing for the
Pharma Data Exchange Hub. Uses Amazon Textract to extract text, tables,
and forms from PDF documents and images, and Amazon Rekognition to detect
defects, labels, and text in images. Parses extraction results into
JSON matching the contract schema, and calculates confidence scores.

Requirements: 7.1, 7.2, 7.3
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.s3_path_utils import generate_bronze_path

logger = logging.getLogger(__name__)

# Supported document types for AI processing
SUPPORTED_DOCUMENT_TYPES = {"pdf", "png", "jpg", "jpeg", "tiff"}

# Supported Textract extraction features
SUPPORTED_EXTRACTION_FEATURES = ["TABLES", "FORMS", "QUERIES"]

# Default confidence threshold (85%)
DEFAULT_CONFIDENCE_THRESHOLD = 0.85

# Default manual review threshold (below this, flag for review)
DEFAULT_MANUAL_REVIEW_THRESHOLD = 0.85

# Output format
OUTPUT_FORMAT = "json"


class AIProcessingError(Exception):
    """Base exception for AI processing operations."""

    def __init__(self, message: str, step: str = "unknown", contract_id: str = ""):
        self.step = step
        self.contract_id = contract_id
        super().__init__(message)


class TextractExtractionError(AIProcessingError):
    """Raised when Textract extraction fails."""
    pass


class DocumentTypeError(AIProcessingError):
    """Raised when document type is unsupported."""
    pass


class ResultParsingError(AIProcessingError):
    """Raised when parsing Textract results fails."""
    pass


class RekognitionDetectionError(AIProcessingError):
    """Raised when Rekognition detection fails."""
    pass


class AIProcessingService:
    """
    Service for Pattern 3: AI-Powered Unstructured Data Processing.

    Manages document type detection, Amazon Textract extraction,
    result parsing into contract-schema-compliant JSON, and
    confidence scoring.
    """

    def __init__(self, textract_client=None, s3_client=None, cloudwatch_client=None, rekognition_client=None):
        """
        Args:
            textract_client: boto3 Textract client (injected for testing).
            s3_client: boto3 S3 client (injected for testing).
            cloudwatch_client: boto3 CloudWatch client (injected for testing).
            rekognition_client: boto3 Rekognition client (injected for testing).
        """
        self._textract = textract_client
        self._s3 = s3_client
        self._cloudwatch = cloudwatch_client
        self._rekognition = rekognition_client

    # ------------------------------------------------------------------
    # Document type detection
    # ------------------------------------------------------------------

    def detect_document_type(self, file_key: str) -> dict:
        """
        Detect document type (PDF or image) based on file extension.

        Args:
            file_key: S3 object key of the uploaded document.

        Returns:
            Dictionary with:
            - documentType: 'pdf' or 'image'
            - extension: file extension (e.g. '.pdf', '.png')
            - fileKey: the original file key
            - supported: True

        Raises:
            DocumentTypeError: If the file extension is not supported.
        """
        if not file_key:
            raise DocumentTypeError(
                "File key cannot be empty",
                step="DetectDocumentType",
            )

        dot_idx = file_key.rfind(".")
        extension = file_key[dot_idx:].lower() if dot_idx != -1 else ""
        ext_no_dot = extension.lstrip(".")

        if ext_no_dot not in SUPPORTED_DOCUMENT_TYPES:
            raise DocumentTypeError(
                f"Unsupported document type '{extension}'. "
                f"Supported: {sorted(SUPPORTED_DOCUMENT_TYPES)}",
                step="DetectDocumentType",
            )

        document_type = "pdf" if ext_no_dot == "pdf" else "image"

        return {
            "documentType": document_type,
            "extension": extension,
            "fileKey": file_key,
            "supported": True,
        }

    # ------------------------------------------------------------------
    # Textract extraction
    # ------------------------------------------------------------------

    def extract_with_textract(
        self, file_key: str, bucket_name: str, contract: dict,
    ) -> dict:
        """
        Call Amazon Textract to extract text, tables, and forms from a
        document stored in S3.

        For PDFs, uses start_document_analysis (async).
        For images, uses analyze_document (sync).

        Args:
            file_key: S3 object key of the document.
            bucket_name: S3 bucket containing the document.
            contract: Data contract dict.

        Returns:
            Dictionary with:
            - textractResponse: raw Textract response (blocks)
            - documentType: 'pdf' or 'image'
            - extractionFeatures: list of features used
            - fileKey, bucketName, contractId

        Raises:
            TextractExtractionError: If extraction fails.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract.get("cmoId", "")

        try:
            doc_info = self.detect_document_type(file_key)
        except DocumentTypeError as exc:
            raise TextractExtractionError(
                str(exc),
                step="ExtractWithTextract",
                contract_id=contract_id,
            ) from exc

        document_type = doc_info["documentType"]
        features = list(SUPPORTED_EXTRACTION_FEATURES)

        if self._textract is None:
            # No client — return a stub response for configuration/testing
            return {
                "textractResponse": {"Blocks": []},
                "documentType": document_type,
                "extractionFeatures": features,
                "fileKey": file_key,
                "bucketName": bucket_name,
                "contractId": contract_id,
                "status": "no_client",
            }

        try:
            s3_object = {"S3Object": {"Bucket": bucket_name, "Name": file_key}}

            if document_type == "pdf":
                response = self._textract.start_document_analysis(
                    DocumentLocation={"S3Object": s3_object["S3Object"]},
                    FeatureTypes=features,
                )
                job_id = response.get("JobId", "")
                # In a real implementation we'd poll for completion.
                # Return the job metadata for the caller to handle.
                return {
                    "textractResponse": response,
                    "jobId": job_id,
                    "documentType": document_type,
                    "extractionFeatures": features,
                    "fileKey": file_key,
                    "bucketName": bucket_name,
                    "contractId": contract_id,
                    "status": "async_started",
                }
            else:
                response = self._textract.analyze_document(
                    Document=s3_object,
                    FeatureTypes=features,
                )
                self._publish_metric(
                    "TextractExtractionCompleted", 1, "Count",
                    contract_id=contract_id, cmo_id=cmo_id,
                )
                return {
                    "textractResponse": response,
                    "documentType": document_type,
                    "extractionFeatures": features,
                    "fileKey": file_key,
                    "bucketName": bucket_name,
                    "contractId": contract_id,
                    "status": "completed",
                }
        except TextractExtractionError:
            raise
        except Exception as exc:
            raise TextractExtractionError(
                f"Textract extraction failed: {exc}",
                step="ExtractWithTextract",
                contract_id=contract_id,
            ) from exc

    # ------------------------------------------------------------------
    # Parse Textract results
    # ------------------------------------------------------------------

    def parse_textract_results(
        self, textract_response: dict, contract: dict,
    ) -> dict:
        """
        Parse a Textract response into JSON matching the contract schema.

        Extracts text lines, tables (as lists of row-dicts), and
        key-value form pairs. Calculates an overall confidence score.

        Args:
            textract_response: Raw Textract response containing Blocks.
            contract: Data contract dict.

        Returns:
            Dictionary with:
            - extractedText: list of text lines
            - extractedTables: list of tables (each a list of row dicts)
            - extractedForms: dict of key-value pairs
            - confidence: overall confidence score (0.0-1.0)
            - blockCount: total number of blocks processed
            - contractId, outputFormat

        Raises:
            ResultParsingError: If parsing fails.
        """
        contract_id = contract.get("contractId", "")

        try:
            blocks = textract_response.get("Blocks", [])

            text_lines: List[str] = []
            tables: List[List[Dict[str, str]]] = []
            forms: Dict[str, str] = {}

            # Index blocks by Id for relationship lookups
            block_map: Dict[str, dict] = {
                b["Id"]: b for b in blocks if "Id" in b
            }

            # Current table tracking
            current_table_cells: Dict[str, Dict[int, Dict[int, str]]] = {}

            for block in blocks:
                block_type = block.get("BlockType", "")

                if block_type == "LINE":
                    text_lines.append(block.get("Text", ""))

                elif block_type == "TABLE":
                    table_id = block.get("Id", "")
                    current_table_cells[table_id] = {}
                    for rel in block.get("Relationships", []):
                        if rel["Type"] == "CHILD":
                            for child_id in rel["Ids"]:
                                child = block_map.get(child_id, {})
                                if child.get("BlockType") == "CELL":
                                    row = child.get("RowIndex", 0)
                                    col = child.get("ColumnIndex", 0)
                                    cell_text = self._get_cell_text(child, block_map)
                                    current_table_cells[table_id].setdefault(row, {})[col] = cell_text

                elif block_type == "KEY_VALUE_SET":
                    entity_type = block.get("EntityTypes", [])
                    if "KEY" in entity_type:
                        key_text = self._get_kv_text(block, block_map, "KEY")
                        value_text = ""
                        for rel in block.get("Relationships", []):
                            if rel["Type"] == "VALUE":
                                for vid in rel["Ids"]:
                                    vblock = block_map.get(vid, {})
                                    value_text = self._get_kv_text(vblock, block_map, "VALUE")
                        if key_text:
                            forms[key_text] = value_text

            # Convert table cells to list-of-row-dicts
            for table_id, rows in current_table_cells.items():
                if not rows:
                    continue
                sorted_rows = sorted(rows.keys())
                # Use first row as headers if available
                header_row = rows.get(sorted_rows[0], {})
                headers = [header_row.get(c, f"col_{c}") for c in sorted(header_row.keys())]
                table_data = []
                for ri in sorted_rows[1:]:
                    row_cells = rows.get(ri, {})
                    row_dict = {}
                    for ci, header in enumerate(headers, start=1):
                        row_dict[header] = row_cells.get(ci, "")
                    table_data.append(row_dict)
                tables.append(table_data)

            confidence = self._calculate_confidence(blocks)

            return {
                "extractedText": text_lines,
                "extractedTables": tables,
                "extractedForms": forms,
                "confidence": confidence,
                "blockCount": len(blocks),
                "contractId": contract_id,
                "outputFormat": OUTPUT_FORMAT,
            }
        except ResultParsingError:
            raise
        except Exception as exc:
            raise ResultParsingError(
                f"Failed to parse Textract results: {exc}",
                step="ParseTextractResults",
                contract_id=contract_id,
            ) from exc

    # ------------------------------------------------------------------
    # Rekognition extraction
    # ------------------------------------------------------------------

    # Image-only extensions (PDFs not supported by Rekognition)
    _REKOGNITION_IMAGE_TYPES = {"png", "jpg", "jpeg", "tiff"}

    def extract_with_rekognition(
        self, file_key: str, bucket_name: str, contract: dict,
    ) -> dict:
        """
        Call Amazon Rekognition to detect labels, text, and defects in
        an image stored in S3.

        Uses ``detect_labels()`` for label/defect detection and
        ``detect_text()`` for text detection. Only works on image types
        (png, jpg, jpeg, tiff); raises an error for PDFs.

        Args:
            file_key: S3 object key of the image.
            bucket_name: S3 bucket containing the image.
            contract: Data contract dict.

        Returns:
            Dictionary with:
            - labelsResponse: raw detect_labels response
            - textResponse: raw detect_text response
            - documentType: 'image'
            - fileKey, bucketName, contractId

        Raises:
            RekognitionDetectionError: If detection fails or file is a PDF.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract.get("cmoId", "")

        # Validate file type — PDFs are not supported by Rekognition
        try:
            doc_info = self.detect_document_type(file_key)
        except DocumentTypeError as exc:
            raise RekognitionDetectionError(
                str(exc),
                step="ExtractWithRekognition",
                contract_id=contract_id,
            ) from exc

        if doc_info["documentType"] == "pdf":
            raise RekognitionDetectionError(
                "Amazon Rekognition does not support PDF files. "
                "Use Textract for PDF processing.",
                step="ExtractWithRekognition",
                contract_id=contract_id,
            )

        if self._rekognition is None:
            # No client — return a stub response for configuration/testing
            return {
                "labelsResponse": {"Labels": []},
                "textResponse": {"TextDetections": []},
                "documentType": "image",
                "fileKey": file_key,
                "bucketName": bucket_name,
                "contractId": contract_id,
                "status": "no_client",
            }

        try:
            s3_object = {"S3Object": {"Bucket": bucket_name, "Name": file_key}}

            labels_response = self._rekognition.detect_labels(
                Image=s3_object,
            )
            text_response = self._rekognition.detect_text(
                Image=s3_object,
            )

            self._publish_metric(
                "RekognitionDetectionCompleted", 1, "Count",
                contract_id=contract_id, cmo_id=cmo_id,
            )

            return {
                "labelsResponse": labels_response,
                "textResponse": text_response,
                "documentType": "image",
                "fileKey": file_key,
                "bucketName": bucket_name,
                "contractId": contract_id,
                "status": "completed",
            }
        except RekognitionDetectionError:
            raise
        except Exception as exc:
            raise RekognitionDetectionError(
                f"Rekognition detection failed: {exc}",
                step="ExtractWithRekognition",
                contract_id=contract_id,
            ) from exc

    # ------------------------------------------------------------------
    # Parse Rekognition results
    # ------------------------------------------------------------------

    def parse_rekognition_results(
        self, rekognition_response: dict, contract: dict,
    ) -> dict:
        """
        Parse a Rekognition response into structured JSON.

        Extracts labels with confidence scores from ``detect_labels``
        and detected text with confidence scores from ``detect_text``.
        Calculates an overall confidence score as the average of all
        individual confidence values.

        Args:
            rekognition_response: Dict with ``labelsResponse`` and
                ``textResponse`` keys (as returned by
                ``extract_with_rekognition``).
            contract: Data contract dict.

        Returns:
            Dictionary with:
            - detectedLabels: list of dicts with name and confidence
            - detectedText: list of dicts with text and confidence
            - confidence: overall confidence score (0.0-1.0)
            - contractId, outputFormat
        """
        contract_id = contract.get("contractId", "")

        labels_resp = rekognition_response.get("labelsResponse", {})
        text_resp = rekognition_response.get("textResponse", {})

        # Extract labels
        detected_labels = []
        for label in labels_resp.get("Labels", []):
            detected_labels.append({
                "name": label.get("Name", ""),
                "confidence": round(label.get("Confidence", 0.0) / 100.0, 4),
            })

        # Extract text (only LINE-type detections to avoid duplicates)
        detected_text = []
        for detection in text_resp.get("TextDetections", []):
            if detection.get("Type") == "LINE":
                detected_text.append({
                    "text": detection.get("DetectedText", ""),
                    "confidence": round(detection.get("Confidence", 0.0) / 100.0, 4),
                })

        # Calculate overall confidence
        all_scores = (
            [l["confidence"] for l in detected_labels]
            + [t["confidence"] for t in detected_text]
        )
        confidence = round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0

        return {
            "detectedLabels": detected_labels,
            "detectedText": detected_text,
            "confidence": confidence,
            "contractId": contract_id,
            "outputFormat": OUTPUT_FORMAT,
        }

    # ------------------------------------------------------------------
    # Confidence thresholding and manual review flagging
    # ------------------------------------------------------------------

    def apply_confidence_thresholding(
        self, parsed_result: dict, contract: dict, bucket_name: str = "cmo-data-lake",
    ) -> dict:
        """
        Apply confidence thresholding to a parsed extraction result.

        If confidence >= DEFAULT_CONFIDENCE_THRESHOLD (0.85), the record
        is routed to the Bronze layer. Otherwise it is flagged for manual
        review and routed to a separate S3 prefix.

        Args:
            parsed_result: Parsed extraction result (from
                ``parse_textract_results`` or ``parse_rekognition_results``).
            contract: Data contract dict (must include cmoId, dataDomain).
            bucket_name: S3 bucket name.

        Returns:
            Dictionary with:
            - destination: 'bronze' or 'manual_review'
            - destinationPath: S3 path for the record
            - needsReview: bool
            - confidence: float
            - contractId, cmoId, dataDomain, processedAt

        Raises:
            AIProcessingError: If contract is missing cmoId or dataDomain.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract.get("cmoId", "")
        data_domain = contract.get("dataDomain", "")

        if not cmo_id:
            raise AIProcessingError(
                "Contract must include cmoId",
                step="ApplyConfidenceThresholding",
                contract_id=contract_id,
            )
        if not data_domain:
            raise AIProcessingError(
                "Contract must include dataDomain",
                step="ApplyConfidenceThresholding",
                contract_id=contract_id,
            )

        confidence = parsed_result.get("confidence", 0.0)
        now = datetime.now(timezone.utc)

        if confidence >= DEFAULT_CONFIDENCE_THRESHOLD:
            destination = "bronze"
            destination_path = generate_bronze_path(
                bucket_name=bucket_name,
                cmo_id=cmo_id,
                data_domain=data_domain,
                date=now,
            )
            needs_review = False
            self._publish_metric(
                "DocumentRoutedToBronze", 1, "Count",
                contract_id=contract_id, cmo_id=cmo_id,
            )
        else:
            destination = "manual_review"
            destination_path = self._generate_review_path(
                bucket_name=bucket_name,
                cmo_id=cmo_id,
                data_domain=data_domain,
                date=now,
            )
            needs_review = True
            self._publish_metric(
                "DocumentFlaggedForReview", 1, "Count",
                contract_id=contract_id, cmo_id=cmo_id,
            )

        return {
            "destination": destination,
            "destinationPath": destination_path,
            "needsReview": needs_review,
            "confidence": confidence,
            "contractId": contract_id,
            "cmoId": cmo_id,
            "dataDomain": data_domain,
            "processedAt": now.isoformat(),
        }

    def _generate_review_path(
        self, bucket_name: str, cmo_id: str, data_domain: str, date: datetime,
    ) -> str:
        """
        Generate S3 path for records flagged for manual review.

        Pattern:
            s3://{bucket_name}/bronze/{cmo_id}/{data_domain}/manual-review/year={YYYY}/month={MM}/day={DD}/
        """
        year = date.strftime("%Y")
        month = date.strftime("%m")
        day = date.strftime("%d")
        return (
            f"s3://{bucket_name}/bronze/{cmo_id}/{data_domain}/"
            f"manual-review/year={year}/month={month}/day={day}/"
        )

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def process_document(
        self,
        event: dict,
        contract: dict,
        bucket_name: str = "cmo-data-lake",
    ) -> dict:
        """
        Main orchestration: detect type, extract, parse, apply confidence
        thresholding, and route to Bronze layer or manual review.

        Args:
            event: Dict with 'file_key' (S3 object key).
            contract: Data contract dict.
            bucket_name: S3 bucket name.

        Returns:
            Processing result with extraction data, confidence,
            bronze path, destination, and review flag.

        Raises:
            AIProcessingError (or subclass) on failure.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract.get("cmoId", "")
        data_domain = contract.get("dataDomain", "")

        if not cmo_id or not data_domain:
            raise AIProcessingError(
                "Contract must include cmoId and dataDomain",
                step="ProcessDocument",
                contract_id=contract_id,
            )

        file_key = event.get("file_key", "")
        if not file_key:
            raise AIProcessingError(
                "Event must include file_key",
                step="ProcessDocument",
                contract_id=contract_id,
            )

        # 1. Detect document type
        doc_info = self.detect_document_type(file_key)

        # 2. Extract with Textract
        extraction = self.extract_with_textract(file_key, bucket_name, contract)

        # 3. Parse results
        parsed = self.parse_textract_results(
            extraction.get("textractResponse", {}), contract,
        )

        # 4. Apply confidence thresholding
        thresholding = self.apply_confidence_thresholding(
            parsed, contract, bucket_name,
        )

        confidence = parsed.get("confidence", 0.0)
        needs_review = thresholding["needsReview"]

        # 5. Generate Bronze path (kept for backward compatibility)
        now = datetime.now(timezone.utc)
        bronze_path = generate_bronze_path(
            bucket_name=bucket_name,
            cmo_id=cmo_id,
            data_domain=data_domain,
            date=now,
        )

        self._publish_metric(
            "DocumentProcessed", 1, "Count",
            contract_id=contract_id, cmo_id=cmo_id,
        )

        return {
            "contractId": contract_id,
            "cmoId": cmo_id,
            "dataDomain": data_domain,
            "fileKey": file_key,
            "documentType": doc_info["documentType"],
            "extractedText": parsed["extractedText"],
            "extractedTables": parsed["extractedTables"],
            "extractedForms": parsed["extractedForms"],
            "confidence": confidence,
            "needsReview": needs_review,
            "bronzePath": bronze_path,
            "destination": thresholding["destination"],
            "destinationPath": thresholding["destinationPath"],
            "outputFormat": OUTPUT_FORMAT,
            "processedAt": now.isoformat(),
            "status": "processed",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_confidence(self, blocks: list) -> float:
        """
        Calculate average confidence from Textract blocks.

        Only considers blocks that carry a Confidence value.
        Returns 0.0 when no scored blocks are present.
        """
        scores = [
            b["Confidence"] / 100.0
            for b in blocks
            if "Confidence" in b
        ]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 4)

    @staticmethod
    def _get_cell_text(cell_block: dict, block_map: dict) -> str:
        """Extract text content from a TABLE CELL block."""
        text_parts: List[str] = []
        for rel in cell_block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for cid in rel["Ids"]:
                    child = block_map.get(cid, {})
                    if child.get("BlockType") == "WORD":
                        text_parts.append(child.get("Text", ""))
        return " ".join(text_parts)

    @staticmethod
    def _get_kv_text(block: dict, block_map: dict, role: str) -> str:
        """Extract text from a KEY_VALUE_SET block (KEY or VALUE side)."""
        text_parts: List[str] = []
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for cid in rel["Ids"]:
                    child = block_map.get(cid, {})
                    if child.get("BlockType") == "WORD":
                        text_parts.append(child.get("Text", ""))
        return " ".join(text_parts)

    def _publish_metric(
        self, metric_name: str, value: float, unit: str,
        contract_id: str = "", cmo_id: str = "",
    ) -> None:
        """Publish a metric to CloudWatch (best-effort)."""
        cw = self._cloudwatch
        if cw is None:
            return
        try:
            cw.put_metric_data(
                Namespace="CMO/DataPipeline",
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": unit,
                        "Dimensions": [
                            {"Name": "ContractId", "Value": contract_id},
                            {"Name": "CMOId", "Value": cmo_id},
                        ],
                    },
                ],
            )
        except Exception as exc:
            logger.warning("Failed to publish CloudWatch metric: %s", exc)
