# Unitime Solver API

A REST API wrapper around the [CPSolver](https://github.com/UniTime/cpsolver) library for university timetabling and scheduling.

## Overview

Unitime Solver API provides a modern REST interface to the powerful CPSolver Java library, enabling easy integration of timetabling functionality into web applications and other services. It handles course scheduling, room assignment, and timetable optimization for educational institutions.

## Features

- REST API for university timetabling operations
- Seamless integration with the CPSolver library
- Input validation and error handling
- Asynchronous solution processing
- Solution persistence and retrieval

## Prerequisites

- Python 3.8+
- Java Runtime Environment (JRE)
- CPSolver library and its dependencies

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/unitime-api.git
cd unitime-api
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

3. Ensure the CPSolver directory is available in one of the following locations:
   - `./cpsolver`
   - `../cpsolver`
   - Or set the `SOLVER_PATH` environment variable to the CPSolver directory

## Setup

Run the setup script to verify your installation:

```bash
python setup_cpsolver.py
```

The script will check for:
- CPSolver directory presence
- Required JAR files
- Java installation
- Create necessary output directories

## Running the API

Start the API server with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.

## API Documentation

Once running, access the auto-generated API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Environment Variables

- `SOLVER_PATH`: Path to the CPSolver directory (optional)
- `LOG_LEVEL`: Set logging level (default: INFO)

## Docker Support

A Dockerfile is provided for containerized deployment:

```bash
docker build -t unitime-api .
docker run -p 8000:8000 -v /path/to/cpsolver:/app/cpsolver unitime-api
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.

## Acknowledgments

- [CPSolver](https://github.com/UniTime/cpsolver) - The core timetabling solver
- [FastAPI](https://fastapi.tiangolo.com/) - The web framework used 