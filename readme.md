# Welsh Government Website Scraper

## Project Overview

This project is a web scraper designed to extract bilingual content (English and Welsh) from the Welsh Government website (https://www.gov.wales/). It automates the process of finding corresponding English and Welsh pages, scraping their content, and saving matched pairs of text for potential use in translation memory systems or corpus linguistics studies.

## Features

- Scrapes the Welsh Government website sitemap to find all available pages
- Identifies pairs of English and Welsh pages
- Extracts content from these page pairs
- Performs quality checks to ensure the extracted content is a valid translation pair
- Saves the extracted bilingual content pairs to a JSONL file
- Utilizes concurrent processing for improved performance
- Implements robust error handling and logging

## Requirements

- Docker
- Docker Compose

## Project Structure

```
project_root/
│
├── script.py              # Main Python script for web scraping
├── Dockerfile             # Dockerfile for building the Python environment
├── docker-compose.yml     # Docker Compose file for easy setup and execution
├── requirements.txt       # Python package dependencies
└── README.md              # This file
```

## How to Use

1. Clone this repository to your local machine.

2. Navigate to the project directory:
   ```
   cd path/to/project_root
   ```

3. Make sure Docker and Docker Compose are installed on your system.

4. Build and run the Docker container using Docker Compose:
   ```
   docker-compose up --build
   ```

   This command will:
   - Build a Docker image based on the Dockerfile
   - Install all necessary Python packages
   - Mount the current directory to `/app` in the container
   - Run the Python script

5. The script will start running, and you'll see log messages in the console indicating its progress.

6. Once the script completes, you'll find the output file `english_welsh_pairs.jsonl` in the `output/` directory.

## Docker Compose File Explanation

The `docker-compose.yml` file is configured as follows:

```yaml
version: '3'
services:
  scraper:
    build: .
    volumes:
      - .:/app
    command: python script.py
```

- `version: '3'`: Specifies the version of the Docker Compose file format.
- `services:`: Defines the services (containers) that make up the application.
  - `scraper:`: The name of our service.
    - `build: .`: Tells Docker Compose to build an image using the Dockerfile in the current directory.
    - `volumes:`: Mounts the current directory to `/app` in the container, allowing for easy file sharing between the host and container.
    - `command: python script.py`: Specifies the command to run when the container starts.

## Output

The script generates a JSONL (JSON Lines) file named `english_welsh_pairs.jsonl` in the `output/` directory. Each line in this file is a JSON object containing:

- `en`: The English text content
- `cy`: The corresponding Welsh text content
- `url`: The URL of the English page where the content was found

## Customization

You can modify the following variables in the `script.py` file to customize the behavior:

- `MAX_WORKERS`: Number of concurrent workers for scraping (default: 20)
- `OUTPUT_DIR`: Directory where the output file will be saved (default: '/app/output')
- `OUTPUT_FILE`: Name of the output file (default: 'english_welsh_pairs.jsonl')
- `REQUEST_DELAY`: Delay between requests in seconds (default: 0.1)

## Notes

- This scraper is designed to be respectful of the target website's resources. It implements delays between requests and uses a session with retries to handle temporary errors.
- The script includes various quality checks to ensure that the extracted text pairs are likely to be valid translations. These checks can be adjusted in the `quality_check` function if needed.
- Logging is set to INFO level by default. You can change it to DEBUG in the script for more detailed logging during development or troubleshooting.

## Disclaimer

Please ensure you have the right to scrape the target website and that you comply with their robots.txt file and terms of service. Use this tool responsibly and consider the load it may place on the target server.