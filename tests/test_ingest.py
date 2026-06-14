import base64
import pytest
from unittest import mock
import requests
from moshpit.exceptions import MoshpitException
from moshpit.ingest import WebScraperIngester, VisualIngester


@pytest.fixture
def mock_ollama_success():
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": '```json\n{"artists": ["Tool - Live", "$uicideboy$", "Motörhead"]}\n```'
    }
    return mock_response


@pytest.fixture
def mock_html_success():
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.text = """
    <html>
      <head><style>.header { color: red; }</style></head>
      <body>
        <nav><a href="/home">Home</a></nav>
        <header><h1>Festival</h1></header>
        <main>
          <div class="lineup">Tool, Deftones, Slipknot</div>
        </main>
        <footer>Footer content</footer>
      </body>
    </html>
    """
    return mock_response


def test_web_scraper_ingester(mock_ollama_success, mock_html_success):
    ingester = WebScraperIngester()

    with mock.patch("requests.get", return_value=mock_html_success) as mock_get:
        with mock.patch("requests.post", return_value=mock_ollama_success) as mock_post:
            artists = ingester.extract_artists("https://festival.com")

            # Assert page was fetched
            mock_get.assert_called_once_with("https://festival.com", timeout=120.0)

            # Assert Ollama was queried with cleaned text (no style, nav, header, footer)
            mock_post.assert_called_once()
            called_json = mock_post.call_args[1]["json"]
            assert "Festival" not in called_json["prompt"]  # stripped header
            assert "Footer" not in called_json["prompt"]  # stripped footer
            assert "Tool, Deftones, Slipknot" in called_json["prompt"]

            # Assert artists list is clean and sanitized
            assert artists == ["Tool", "Suicideboys", "Motorhead"]


def test_web_scraper_fetch_failure():
    ingester = WebScraperIngester()
    with mock.patch(
        "requests.get", side_effect=requests.RequestException("Network Down")
    ):
        with pytest.raises(MoshpitException, match="Failed to fetch webpage"):
            ingester.extract_artists("https://festival.com")


def test_web_scraper_empty_content(mock_html_success):
    ingester = WebScraperIngester()
    mock_html_success.text = (
        "<html><body><style>body { color: red; }</style></body></html>"
    )
    with mock.patch("requests.get", return_value=mock_html_success):
        with pytest.raises(MoshpitException, match="yielded no readable text"):
            ingester.extract_artists("https://festival.com")


def test_visual_ingester_success(tmp_path, mock_ollama_success):
    image_file = tmp_path / "poster.png"
    image_file.write_bytes(b"dummy_image_data")

    ingester = VisualIngester()

    with mock.patch("requests.post", return_value=mock_ollama_success) as mock_post:
        artists = ingester.extract_artists(str(image_file))

        mock_post.assert_called_once()
        called_json = mock_post.call_args[1]["json"]
        assert called_json["images"] == [
            base64.b64encode(b"dummy_image_data").decode("utf-8")
        ]
        assert artists == ["Tool", "Suicideboys", "Motorhead"]


def test_visual_ingester_file_not_found():
    ingester = VisualIngester()
    with pytest.raises(MoshpitException, match="Concert poster image not found"):
        ingester.extract_artists("nonexistent_poster.png")


def test_query_ollama_retry_behavior():
    ingester = WebScraperIngester()

    # We want to mock post to fail 2 times and succeed on the 3rd attempt
    fail_response = requests.RequestException("Ollama Timeout")

    success_response = mock.Mock()
    success_response.status_code = 200
    success_response.json.return_value = {"response": '{"artists": ["Tool"]}'}

    # Patch requests.post with side effects
    with mock.patch(
        "requests.post", side_effect=[fail_response, fail_response, success_response]
    ) as mock_post:
        # We also mock tenacity's wait to speed up tests
        with mock.patch("tenacity.nap.time.sleep", return_value=None):
            result = ingester.query_ollama("extract artists")
            assert result == '{"artists": ["Tool"]}'
            assert mock_post.call_count == 3


def test_query_ollama_failures():
    ingester = WebScraperIngester()

    # 3 failures in a row (exceeding retry limit)
    fail_response = requests.RequestException("Ollama Offline")
    with mock.patch("requests.post", side_effect=fail_response) as mock_post:
        with mock.patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(MoshpitException, match="Failed to query Ollama API"):
                ingester.query_ollama("extract artists")
            assert mock_post.call_count == 3


def test_validation_schema_errors():
    ingester = WebScraperIngester()

    # 1. Ollama empty response
    empty_response = mock.Mock()
    empty_response.status_code = 200
    empty_response.json.return_value = {"response": ""}

    with mock.patch("requests.post", return_value=empty_response):
        with pytest.raises(
            MoshpitException, match="Ollama returned an empty response string"
        ):
            ingester.query_ollama("test")

    # 2. Ollama invalid schema response (missing artists key)
    invalid_schema_output = '{"bands": ["Tool"]}'
    with pytest.raises(MoshpitException, match="Failed to validate LLM response"):
        ingester.parse_and_validate_artists(invalid_schema_output)

    # 3. Ollama response resolving to 0 valid artists after sanitation
    no_valid_artists = '{"artists": ["", "  ", "- Live"]}'
    with pytest.raises(MoshpitException, match="resolved zero valid artists"):
        ingester.parse_and_validate_artists(no_valid_artists)


def test_visual_ingester_read_failure(tmp_path):
    image_file = tmp_path / "poster.png"
    image_file.write_bytes(b"dummy_image_data")

    ingester = VisualIngester()

    with mock.patch("builtins.open", side_effect=IOError("Read Error")):
        with pytest.raises(MoshpitException, match="Failed to read image file"):
            ingester.extract_artists(str(image_file))
