"""
Unit Tests for AIProcessingService.

Validates:
- Document type detection (PDF vs image)
- Textract extraction (text, tables, forms)
- Textract result parsing into contract-schema JSON
- Confidence score calculation
- Rekognition extraction (labels, text, defects)
- Rekognition result parsing
- End-to-end document processing orchestration
- CloudWatch metric publishing
- Exception hierarchy

Requirements: 7.1, 7.2, 7.3
"""
import sys
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.ai_processing_service import (
    AIProcessingService,
    AIProcessingError,
    TextractExtractionError,
    DocumentTypeError,
    ResultParsingError,
    RekognitionDetectionError,
    SUPPORTED_DOCUMENT_TYPES,
    SUPPORTED_EXTRACTION_FEATURES,
    DEFAULT_CONFIDENCE_THRESHOLD,
    OUTPUT_FORMAT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contract(**overrides):
    """Return a minimal contract for testing."""
    contract = {
        "contractId": "CMO-ALPHA-DOCS-001",
        "cmoId": "cmo-alpha",
        "dataDomain": "batch-records",
        "integrationPattern": "ai-unstructured",
        "status": "active",
    }
    contract.update(overrides)
    return contract


def _textract_response(blocks=None):
    """Return a minimal Textract response."""
    if blocks is None:
        blocks = [
            {
                "Id": "line-1",
                "BlockType": "LINE",
                "Text": "Batch Record 12345",
                "Confidence": 99.5,
            },
            {
                "Id": "line-2",
                "BlockType": "LINE",
                "Text": "Product: Aspirin 500mg",
                "Confidence": 98.0,
            },
        ]
    return {"Blocks": blocks}


def _table_blocks():
    """Return Textract blocks representing a simple table."""
    return [
        {
            "Id": "table-1",
            "BlockType": "TABLE",
            "Confidence": 95.0,
            "Relationships": [
                {"Type": "CHILD", "Ids": ["cell-1-1", "cell-1-2", "cell-2-1", "cell-2-2"]},
            ],
        },
        {
            "Id": "cell-1-1",
            "BlockType": "CELL",
            "RowIndex": 1,
            "ColumnIndex": 1,
            "Confidence": 95.0,
            "Relationships": [{"Type": "CHILD", "Ids": ["word-h1"]}],
        },
        {
            "Id": "cell-1-2",
            "BlockType": "CELL",
            "RowIndex": 1,
            "ColumnIndex": 2,
            "Confidence": 94.0,
            "Relationships": [{"Type": "CHILD", "Ids": ["word-h2"]}],
        },
        {
            "Id": "cell-2-1",
            "BlockType": "CELL",
            "RowIndex": 2,
            "ColumnIndex": 1,
            "Confidence": 93.0,
            "Relationships": [{"Type": "CHILD", "Ids": ["word-d1"]}],
        },
        {
            "Id": "cell-2-2",
            "BlockType": "CELL",
            "RowIndex": 2,
            "ColumnIndex": 2,
            "Confidence": 92.0,
            "Relationships": [{"Type": "CHILD", "Ids": ["word-d2"]}],
        },
        {"Id": "word-h1", "BlockType": "WORD", "Text": "BatchID", "Confidence": 99.0},
        {"Id": "word-h2", "BlockType": "WORD", "Text": "Status", "Confidence": 98.0},
        {"Id": "word-d1", "BlockType": "WORD", "Text": "B001", "Confidence": 97.0},
        {"Id": "word-d2", "BlockType": "WORD", "Text": "PASS", "Confidence": 96.0},
    ]


def _form_blocks():
    """Return Textract blocks representing key-value form pairs."""
    return [
        {
            "Id": "kv-key-1",
            "BlockType": "KEY_VALUE_SET",
            "EntityTypes": ["KEY"],
            "Confidence": 97.0,
            "Relationships": [
                {"Type": "CHILD", "Ids": ["word-key-1"]},
                {"Type": "VALUE", "Ids": ["kv-val-1"]},
            ],
        },
        {
            "Id": "kv-val-1",
            "BlockType": "KEY_VALUE_SET",
            "EntityTypes": ["VALUE"],
            "Confidence": 96.0,
            "Relationships": [
                {"Type": "CHILD", "Ids": ["word-val-1"]},
            ],
        },
        {"Id": "word-key-1", "BlockType": "WORD", "Text": "Product", "Confidence": 99.0},
        {"Id": "word-val-1", "BlockType": "WORD", "Text": "Aspirin", "Confidence": 98.0},
    ]


@pytest.fixture
def service():
    return AIProcessingService()


# ---------------------------------------------------------------------------
# Document type detection
# ---------------------------------------------------------------------------

class TestDetectDocumentType:
    """Requirement 7.1: Detect document type (PDF vs image)."""

    def test_pdf_detected(self, service):
        result = service.detect_document_type("docs/report.pdf")
        assert result["documentType"] == "pdf"
        assert result["extension"] == ".pdf"
        assert result["supported"] is True

    def test_png_detected_as_image(self, service):
        result = service.detect_document_type("images/scan.png")
        assert result["documentType"] == "image"
        assert result["extension"] == ".png"

    def test_jpg_detected_as_image(self, service):
        result = service.detect_document_type("images/photo.jpg")
        assert result["documentType"] == "image"

    def test_jpeg_detected_as_image(self, service):
        result = service.detect_document_type("images/photo.jpeg")
        assert result["documentType"] == "image"
        assert result["extension"] == ".jpeg"

    def test_tiff_detected_as_image(self, service):
        result = service.detect_document_type("scans/doc.tiff")
        assert result["documentType"] == "image"

    def test_uppercase_extension(self, service):
        result = service.detect_document_type("docs/REPORT.PDF")
        assert result["documentType"] == "pdf"

    def test_mixed_case_extension(self, service):
        result = service.detect_document_type("docs/scan.Png")
        assert result["documentType"] == "image"

    def test_unsupported_extension_raises(self, service):
        with pytest.raises(DocumentTypeError, match="Unsupported document type"):
            service.detect_document_type("data/file.xlsx")

    def test_no_extension_raises(self, service):
        with pytest.raises(DocumentTypeError, match="Unsupported document type"):
            service.detect_document_type("data/noextension")

    def test_empty_file_key_raises(self, service):
        with pytest.raises(DocumentTypeError, match="cannot be empty"):
            service.detect_document_type("")

    def test_file_key_preserved_in_result(self, service):
        result = service.detect_document_type("path/to/doc.pdf")
        assert result["fileKey"] == "path/to/doc.pdf"


# ---------------------------------------------------------------------------
# Textract extraction
# ---------------------------------------------------------------------------

class TestExtractWithTextract:
    """Requirement 7.1: Extract text, tables, and forms using Textract."""

    def test_no_client_returns_stub(self, service):
        result = service.extract_with_textract(
            "doc.png", "my-bucket", _contract(),
        )
        assert result["status"] == "no_client"
        assert result["documentType"] == "image"
        assert result["extractionFeatures"] == SUPPORTED_EXTRACTION_FEATURES

    def test_image_uses_analyze_document(self):
        mock_textract = MagicMock()
        mock_textract.analyze_document.return_value = {"Blocks": []}
        svc = AIProcessingService(textract_client=mock_textract)

        result = svc.extract_with_textract("scan.png", "bucket", _contract())

        mock_textract.analyze_document.assert_called_once()
        assert result["status"] == "completed"
        assert result["documentType"] == "image"

    def test_pdf_uses_start_document_analysis(self):
        mock_textract = MagicMock()
        mock_textract.start_document_analysis.return_value = {"JobId": "job-123"}
        svc = AIProcessingService(textract_client=mock_textract)

        result = svc.extract_with_textract("report.pdf", "bucket", _contract())

        mock_textract.start_document_analysis.assert_called_once()
        assert result["status"] == "async_started"
        assert result["jobId"] == "job-123"

    def test_contract_id_in_result(self):
        mock_textract = MagicMock()
        mock_textract.analyze_document.return_value = {"Blocks": []}
        svc = AIProcessingService(textract_client=mock_textract)

        result = svc.extract_with_textract("img.jpg", "bucket", _contract())
        assert result["contractId"] == "CMO-ALPHA-DOCS-001"

    def test_unsupported_type_raises(self, service):
        with pytest.raises(TextractExtractionError):
            service.extract_with_textract("file.xlsx", "bucket", _contract())

    def test_textract_api_error_raises(self):
        mock_textract = MagicMock()
        mock_textract.analyze_document.side_effect = Exception("Textract down")
        svc = AIProcessingService(textract_client=mock_textract)

        with pytest.raises(TextractExtractionError, match="Textract extraction failed"):
            svc.extract_with_textract("scan.png", "bucket", _contract())

    def test_cloudwatch_metric_on_image_extraction(self):
        mock_textract = MagicMock()
        mock_textract.analyze_document.return_value = {"Blocks": []}
        mock_cw = MagicMock()
        svc = AIProcessingService(textract_client=mock_textract, cloudwatch_client=mock_cw)

        svc.extract_with_textract("scan.png", "bucket", _contract())
        mock_cw.put_metric_data.assert_called_once()

    def test_extraction_features_included(self):
        mock_textract = MagicMock()
        mock_textract.analyze_document.return_value = {"Blocks": []}
        svc = AIProcessingService(textract_client=mock_textract)

        result = svc.extract_with_textract("scan.jpg", "bucket", _contract())
        assert "TABLES" in result["extractionFeatures"]
        assert "FORMS" in result["extractionFeatures"]


# ---------------------------------------------------------------------------
# Parse Textract results
# ---------------------------------------------------------------------------

class TestParseTextractResults:
    """Requirement 7.2: Parse extracted data into JSON matching contract schema."""

    def test_extracts_text_lines(self, service):
        response = _textract_response()
        result = service.parse_textract_results(response, _contract())
        assert "Batch Record 12345" in result["extractedText"]
        assert "Product: Aspirin 500mg" in result["extractedText"]

    def test_calculates_confidence(self, service):
        response = _textract_response()
        result = service.parse_textract_results(response, _contract())
        # (99.5 + 98.0) / 2 / 100 = 0.9875
        assert 0.98 <= result["confidence"] <= 0.99

    def test_empty_blocks_returns_zero_confidence(self, service):
        result = service.parse_textract_results({"Blocks": []}, _contract())
        assert result["confidence"] == 0.0
        assert result["extractedText"] == []
        assert result["extractedTables"] == []
        assert result["extractedForms"] == {}

    def test_output_format_is_json(self, service):
        result = service.parse_textract_results({"Blocks": []}, _contract())
        assert result["outputFormat"] == OUTPUT_FORMAT

    def test_contract_id_in_result(self, service):
        result = service.parse_textract_results({"Blocks": []}, _contract())
        assert result["contractId"] == "CMO-ALPHA-DOCS-001"

    def test_block_count(self, service):
        response = _textract_response()
        result = service.parse_textract_results(response, _contract())
        assert result["blockCount"] == 2

    def test_parses_table_blocks(self, service):
        blocks = _table_blocks()
        result = service.parse_textract_results({"Blocks": blocks}, _contract())
        assert len(result["extractedTables"]) == 1
        table = result["extractedTables"][0]
        assert len(table) == 1  # one data row (row 2)
        assert table[0]["BatchID"] == "B001"
        assert table[0]["Status"] == "PASS"

    def test_parses_form_blocks(self, service):
        blocks = _form_blocks()
        result = service.parse_textract_results({"Blocks": blocks}, _contract())
        assert result["extractedForms"]["Product"] == "Aspirin"

    def test_mixed_blocks(self, service):
        blocks = (
            [{"Id": "l1", "BlockType": "LINE", "Text": "Header", "Confidence": 99.0}]
            + _table_blocks()
            + _form_blocks()
        )
        result = service.parse_textract_results({"Blocks": blocks}, _contract())
        assert "Header" in result["extractedText"]
        assert len(result["extractedTables"]) == 1
        assert "Product" in result["extractedForms"]

    def test_confidence_with_low_scores(self, service):
        blocks = [
            {"Id": "b1", "BlockType": "LINE", "Text": "blurry", "Confidence": 40.0},
            {"Id": "b2", "BlockType": "LINE", "Text": "unclear", "Confidence": 50.0},
        ]
        result = service.parse_textract_results({"Blocks": blocks}, _contract())
        assert result["confidence"] < DEFAULT_CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Process document (orchestration)
# ---------------------------------------------------------------------------

class TestProcessDocument:
    """Requirements 7.1, 7.2: End-to-end document processing."""

    def test_successful_processing(self, service):
        result = service.process_document(
            {"file_key": "incoming/report.pdf"},
            _contract(),
        )
        assert result["status"] == "processed"
        assert result["contractId"] == "CMO-ALPHA-DOCS-001"
        assert result["documentType"] == "pdf"

    def test_bronze_path_generated(self, service):
        result = service.process_document(
            {"file_key": "incoming/scan.png"},
            _contract(),
        )
        assert "bronze" in result["bronzePath"]
        assert "cmo-alpha" in result["bronzePath"]

    def test_processed_at_timestamp(self, service):
        result = service.process_document(
            {"file_key": "incoming/doc.jpg"},
            _contract(),
        )
        assert "processedAt" in result

    def test_output_format(self, service):
        result = service.process_document(
            {"file_key": "incoming/doc.tiff"},
            _contract(),
        )
        assert result["outputFormat"] == "json"

    def test_needs_review_when_low_confidence(self, service):
        # No textract client → empty blocks → confidence 0.0
        result = service.process_document(
            {"file_key": "incoming/blurry.png"},
            _contract(),
        )
        assert result["needsReview"] is True

    def test_no_review_when_high_confidence(self):
        mock_textract = MagicMock()
        mock_textract.analyze_document.return_value = {
            "Blocks": [
                {"Id": "b1", "BlockType": "LINE", "Text": "clear", "Confidence": 99.0},
            ],
        }
        svc = AIProcessingService(textract_client=mock_textract)
        result = svc.process_document(
            {"file_key": "incoming/clear.png"},
            _contract(),
        )
        assert result["needsReview"] is False
        assert result["confidence"] >= DEFAULT_CONFIDENCE_THRESHOLD

    def test_missing_cmo_id_raises(self, service):
        with pytest.raises(AIProcessingError, match="cmoId and dataDomain"):
            service.process_document(
                {"file_key": "doc.pdf"},
                _contract(cmoId=""),
            )

    def test_missing_data_domain_raises(self, service):
        with pytest.raises(AIProcessingError, match="cmoId and dataDomain"):
            service.process_document(
                {"file_key": "doc.pdf"},
                _contract(dataDomain=""),
            )

    def test_missing_file_key_raises(self, service):
        with pytest.raises(AIProcessingError, match="file_key"):
            service.process_document({}, _contract())

    def test_unsupported_file_raises(self, service):
        with pytest.raises(DocumentTypeError):
            service.process_document(
                {"file_key": "data.xlsx"},
                _contract(),
            )

    def test_cloudwatch_metrics_published(self):
        mock_cw = MagicMock()
        svc = AIProcessingService(cloudwatch_client=mock_cw)
        svc.process_document(
            {"file_key": "incoming/doc.pdf"},
            _contract(),
        )
        # At least DocumentProcessed + DocumentFlaggedForReview (confidence=0)
        assert mock_cw.put_metric_data.call_count >= 1

    def test_cloudwatch_failure_does_not_raise(self):
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = Exception("CW unavailable")
        svc = AIProcessingService(cloudwatch_client=mock_cw)
        result = svc.process_document(
            {"file_key": "incoming/doc.pdf"},
            _contract(),
        )
        assert result["status"] == "processed"


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------

class TestCalculateConfidence:
    """Test _calculate_confidence helper."""

    def test_average_of_scores(self, service):
        blocks = [
            {"Confidence": 90.0},
            {"Confidence": 80.0},
        ]
        assert service._calculate_confidence(blocks) == 0.85

    def test_single_block(self, service):
        blocks = [{"Confidence": 95.0}]
        assert service._calculate_confidence(blocks) == 0.95

    def test_empty_blocks(self, service):
        assert service._calculate_confidence([]) == 0.0

    def test_blocks_without_confidence_ignored(self, service):
        blocks = [
            {"Confidence": 90.0},
            {"BlockType": "PAGE"},  # no Confidence key
        ]
        assert service._calculate_confidence(blocks) == 0.9

    def test_perfect_confidence(self, service):
        blocks = [{"Confidence": 100.0}]
        assert service._calculate_confidence(blocks) == 1.0

    def test_zero_confidence(self, service):
        blocks = [{"Confidence": 0.0}]
        assert service._calculate_confidence(blocks) == 0.0


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    def test_textract_error_is_ai_processing_error(self):
        assert issubclass(TextractExtractionError, AIProcessingError)

    def test_document_type_error_is_ai_processing_error(self):
        assert issubclass(DocumentTypeError, AIProcessingError)

    def test_result_parsing_error_is_ai_processing_error(self):
        assert issubclass(ResultParsingError, AIProcessingError)

    def test_rekognition_error_is_ai_processing_error(self):
        assert issubclass(RekognitionDetectionError, AIProcessingError)

    def test_error_includes_step_and_contract_id(self):
        err = TextractExtractionError(
            "bad", step="ExtractWithTextract", contract_id="CMO-001",
        )
        assert err.step == "ExtractWithTextract"
        assert err.contract_id == "CMO-001"

    def test_rekognition_error_includes_step_and_contract_id(self):
        err = RekognitionDetectionError(
            "fail", step="ExtractWithRekognition", contract_id="CMO-002",
        )
        assert err.step == "ExtractWithRekognition"
        assert err.contract_id == "CMO-002"

    def test_base_error_defaults(self):
        err = AIProcessingError("test")
        assert err.step == "unknown"
        assert err.contract_id == ""


# ---------------------------------------------------------------------------
# Rekognition extraction
# ---------------------------------------------------------------------------

class TestExtractWithRekognition:
    """Requirement 7.3: Detect defects, labels, and text in images."""

    def test_no_client_returns_stub(self, service):
        result = service.extract_with_rekognition(
            "scan.png", "my-bucket", _contract(),
        )
        assert result["status"] == "no_client"
        assert result["documentType"] == "image"
        assert result["labelsResponse"] == {"Labels": []}
        assert result["textResponse"] == {"TextDetections": []}

    def test_label_detection_called(self):
        mock_rek = MagicMock()
        mock_rek.detect_labels.return_value = {"Labels": []}
        mock_rek.detect_text.return_value = {"TextDetections": []}
        svc = AIProcessingService(rekognition_client=mock_rek)

        result = svc.extract_with_rekognition("scan.png", "bucket", _contract())

        mock_rek.detect_labels.assert_called_once()
        assert result["status"] == "completed"

    def test_text_detection_called(self):
        mock_rek = MagicMock()
        mock_rek.detect_labels.return_value = {"Labels": []}
        mock_rek.detect_text.return_value = {"TextDetections": []}
        svc = AIProcessingService(rekognition_client=mock_rek)

        svc.extract_with_rekognition("scan.jpg", "bucket", _contract())

        mock_rek.detect_text.assert_called_once()

    def test_pdf_raises_error(self, service):
        with pytest.raises(RekognitionDetectionError, match="does not support PDF"):
            service.extract_with_rekognition("report.pdf", "bucket", _contract())

    def test_api_error_raises(self):
        mock_rek = MagicMock()
        mock_rek.detect_labels.side_effect = Exception("Rekognition down")
        svc = AIProcessingService(rekognition_client=mock_rek)

        with pytest.raises(RekognitionDetectionError, match="Rekognition detection failed"):
            svc.extract_with_rekognition("scan.png", "bucket", _contract())

    def test_cloudwatch_metric_on_detection(self):
        mock_rek = MagicMock()
        mock_rek.detect_labels.return_value = {"Labels": []}
        mock_rek.detect_text.return_value = {"TextDetections": []}
        mock_cw = MagicMock()
        svc = AIProcessingService(rekognition_client=mock_rek, cloudwatch_client=mock_cw)

        svc.extract_with_rekognition("scan.png", "bucket", _contract())
        mock_cw.put_metric_data.assert_called_once()

    def test_contract_id_in_result(self):
        mock_rek = MagicMock()
        mock_rek.detect_labels.return_value = {"Labels": []}
        mock_rek.detect_text.return_value = {"TextDetections": []}
        svc = AIProcessingService(rekognition_client=mock_rek)

        result = svc.extract_with_rekognition("img.jpg", "bucket", _contract())
        assert result["contractId"] == "CMO-ALPHA-DOCS-001"

    def test_unsupported_extension_raises(self, service):
        with pytest.raises(RekognitionDetectionError):
            service.extract_with_rekognition("file.xlsx", "bucket", _contract())

    def test_tiff_supported(self):
        mock_rek = MagicMock()
        mock_rek.detect_labels.return_value = {"Labels": []}
        mock_rek.detect_text.return_value = {"TextDetections": []}
        svc = AIProcessingService(rekognition_client=mock_rek)

        result = svc.extract_with_rekognition("scan.tiff", "bucket", _contract())
        assert result["status"] == "completed"
        assert result["documentType"] == "image"


# ---------------------------------------------------------------------------
# Parse Rekognition results
# ---------------------------------------------------------------------------

class TestParseRekognitionResults:
    """Requirement 7.3: Parse Rekognition detection results into JSON."""

    def test_extracts_labels(self, service):
        response = {
            "labelsResponse": {
                "Labels": [
                    {"Name": "Pill", "Confidence": 98.0},
                    {"Name": "Defect", "Confidence": 72.0},
                ],
            },
            "textResponse": {"TextDetections": []},
        }
        result = service.parse_rekognition_results(response, _contract())
        assert len(result["detectedLabels"]) == 2
        assert result["detectedLabels"][0]["name"] == "Pill"
        assert result["detectedLabels"][0]["confidence"] == 0.98

    def test_extracts_text(self, service):
        response = {
            "labelsResponse": {"Labels": []},
            "textResponse": {
                "TextDetections": [
                    {"DetectedText": "Batch 12345", "Confidence": 95.0, "Type": "LINE"},
                    {"DetectedText": "Batch", "Confidence": 96.0, "Type": "WORD"},
                ],
            },
        }
        result = service.parse_rekognition_results(response, _contract())
        # Only LINE type should be included
        assert len(result["detectedText"]) == 1
        assert result["detectedText"][0]["text"] == "Batch 12345"
        assert result["detectedText"][0]["confidence"] == 0.95

    def test_confidence_calculation(self, service):
        response = {
            "labelsResponse": {
                "Labels": [{"Name": "A", "Confidence": 90.0}],
            },
            "textResponse": {
                "TextDetections": [
                    {"DetectedText": "X", "Confidence": 80.0, "Type": "LINE"},
                ],
            },
        }
        result = service.parse_rekognition_results(response, _contract())
        # (0.9 + 0.8) / 2 = 0.85
        assert result["confidence"] == 0.85

    def test_empty_results(self, service):
        response = {
            "labelsResponse": {"Labels": []},
            "textResponse": {"TextDetections": []},
        }
        result = service.parse_rekognition_results(response, _contract())
        assert result["confidence"] == 0.0
        assert result["detectedLabels"] == []
        assert result["detectedText"] == []

    def test_contract_id_in_result(self, service):
        response = {
            "labelsResponse": {"Labels": []},
            "textResponse": {"TextDetections": []},
        }
        result = service.parse_rekognition_results(response, _contract())
        assert result["contractId"] == "CMO-ALPHA-DOCS-001"

    def test_output_format(self, service):
        response = {
            "labelsResponse": {"Labels": []},
            "textResponse": {"TextDetections": []},
        }
        result = service.parse_rekognition_results(response, _contract())
        assert result["outputFormat"] == OUTPUT_FORMAT


# ---------------------------------------------------------------------------
# Confidence thresholding (Task 9.3)
# ---------------------------------------------------------------------------

class TestApplyConfidenceThresholding:
    """Requirements 7.5, 7.6: Confidence thresholding and manual review flagging."""

    def _parsed(self, confidence=0.90):
        return {
            "confidence": confidence,
            "extractedText": ["sample"],
            "extractedTables": [],
            "extractedForms": {},
            "contractId": "CMO-ALPHA-DOCS-001",
            "outputFormat": "json",
        }

    def test_high_confidence_goes_to_bronze(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(0.95), _contract(),
        )
        assert result["destination"] == "bronze"
        assert result["needsReview"] is False

    def test_low_confidence_goes_to_review(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(0.50), _contract(),
        )
        assert result["destination"] == "manual_review"
        assert result["needsReview"] is True

    def test_exact_threshold_goes_to_bronze(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(0.85), _contract(),
        )
        assert result["destination"] == "bronze"
        assert result["needsReview"] is False

    def test_zero_confidence_goes_to_review(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(0.0), _contract(),
        )
        assert result["destination"] == "manual_review"
        assert result["needsReview"] is True

    def test_perfect_confidence_goes_to_bronze(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(1.0), _contract(),
        )
        assert result["destination"] == "bronze"
        assert result["needsReview"] is False

    def test_bronze_path_format(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(0.95), _contract(),
        )
        assert "bronze" in result["destinationPath"]
        assert "cmo-alpha" in result["destinationPath"]
        assert "batch-records" in result["destinationPath"]

    def test_review_path_format(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(0.50), _contract(),
        )
        assert "manual-review" in result["destinationPath"]

    def test_contract_id_in_result(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(0.90), _contract(),
        )
        assert result["contractId"] == "CMO-ALPHA-DOCS-001"

    def test_cmo_id_in_result(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(0.90), _contract(),
        )
        assert result["cmoId"] == "cmo-alpha"

    def test_processed_at_timestamp(self, service):
        result = service.apply_confidence_thresholding(
            self._parsed(0.90), _contract(),
        )
        assert "processedAt" in result
        assert len(result["processedAt"]) > 0

    def test_cloudwatch_metric_for_bronze(self):
        mock_cw = MagicMock()
        svc = AIProcessingService(cloudwatch_client=mock_cw)
        svc.apply_confidence_thresholding(self._parsed(0.95), _contract())
        mock_cw.put_metric_data.assert_called_once()
        call_args = mock_cw.put_metric_data.call_args
        metric_name = call_args[1]["MetricData"][0]["MetricName"] if "MetricData" in call_args[1] else call_args[0][0]
        assert "Bronze" in metric_name or "bronze" in str(call_args).lower() or "DocumentRoutedToBronze" in str(call_args)

    def test_cloudwatch_metric_for_review(self):
        mock_cw = MagicMock()
        svc = AIProcessingService(cloudwatch_client=mock_cw)
        svc.apply_confidence_thresholding(self._parsed(0.50), _contract())
        mock_cw.put_metric_data.assert_called_once()
        call_args = mock_cw.put_metric_data.call_args
        assert "FlaggedForReview" in str(call_args)

    def test_cloudwatch_failure_does_not_raise(self):
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = Exception("CW unavailable")
        svc = AIProcessingService(cloudwatch_client=mock_cw)
        result = svc.apply_confidence_thresholding(self._parsed(0.95), _contract())
        assert result["destination"] == "bronze"

    def test_missing_cmo_id_raises(self, service):
        with pytest.raises(AIProcessingError):
            service.apply_confidence_thresholding(
                self._parsed(0.90), _contract(cmoId=""),
            )

    def test_missing_data_domain_raises(self, service):
        with pytest.raises(AIProcessingError):
            service.apply_confidence_thresholding(
                self._parsed(0.90), _contract(dataDomain=""),
            )


# ---------------------------------------------------------------------------
# Generate review path (Task 9.3)
# ---------------------------------------------------------------------------

class TestGenerateReviewPath:
    """Test _generate_review_path helper."""

    def test_path_format(self, service):
        dt = datetime(2024, 3, 15, tzinfo=timezone.utc)
        path = service._generate_review_path("cmo-data-lake", "cmo-alpha", "batch-records", dt)
        assert path == "s3://cmo-data-lake/bronze/cmo-alpha/batch-records/manual-review/year=2024/month=03/day=15/"

    def test_path_contains_bucket(self, service):
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        path = service._generate_review_path("my-bucket", "cmo-alpha", "batch-records", dt)
        assert "my-bucket" in path

    def test_path_contains_cmo_id(self, service):
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        path = service._generate_review_path("bucket", "cmo-beta", "quality-data", dt)
        assert "cmo-beta" in path

    def test_path_contains_manual_review(self, service):
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        path = service._generate_review_path("bucket", "cmo-alpha", "batch-records", dt)
        assert "manual-review" in path


# ---------------------------------------------------------------------------
# Updated TestProcessDocument checks for destination fields (Task 9.3)
# ---------------------------------------------------------------------------

class TestProcessDocumentDestination:
    """Requirements 7.5, 7.6: process_document includes destination fields."""

    def test_destination_field_present(self, service):
        result = service.process_document(
            {"file_key": "incoming/report.pdf"}, _contract(),
        )
        assert "destination" in result

    def test_destination_path_field_present(self, service):
        result = service.process_document(
            {"file_key": "incoming/report.pdf"}, _contract(),
        )
        assert "destinationPath" in result

    def test_low_confidence_destination_is_manual_review(self, service):
        # No textract client → empty blocks → confidence 0.0
        result = service.process_document(
            {"file_key": "incoming/blurry.png"}, _contract(),
        )
        assert result["destination"] == "manual_review"
        assert "manual-review" in result["destinationPath"]

    def test_high_confidence_destination_is_bronze(self):
        mock_textract = MagicMock()
        mock_textract.analyze_document.return_value = {
            "Blocks": [
                {"Id": "b1", "BlockType": "LINE", "Text": "clear", "Confidence": 99.0},
            ],
        }
        svc = AIProcessingService(textract_client=mock_textract)
        result = svc.process_document(
            {"file_key": "incoming/clear.png"}, _contract(),
        )
        assert result["destination"] == "bronze"
        assert "bronze" in result["destinationPath"]
