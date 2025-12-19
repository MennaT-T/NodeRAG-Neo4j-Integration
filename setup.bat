@echo off
REM ============================================================================
REM NodeRAG Setup Script for Teammates (Windows)
REM ============================================================================

echo.
echo ============================================
echo   NodeRAG API Setup
echo ============================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo.
    echo [IMPORTANT] Please edit .env file and add your API keys!
    echo   - GOOGLE_API_KEY=your-key-here
    echo   - or OPENAI_API_KEY=your-key-here
    echo.
    notepad .env
    pause
)

REM Pull and start containers
echo.
echo Starting NodeRAG services...
docker-compose -f docker-compose.prod.yml up -d

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo   API:          http://localhost:8000
echo   API Docs:     http://localhost:8000/docs
echo   Neo4j:        http://localhost:7474
echo.
echo   Commands:
echo     View logs:  docker-compose -f docker-compose.prod.yml logs -f
echo     Stop:       docker-compose -f docker-compose.prod.yml down
echo.
pause
