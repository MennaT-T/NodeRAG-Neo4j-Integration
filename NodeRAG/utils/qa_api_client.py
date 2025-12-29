"""
API client for Q&A history integration.
Calls backend API to fetch Q&A pairs, with mock JSON file for development.
"""
import json
import os
from typing import List, Dict, Optional
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

class QAAPIClient:
    """Client for fetching Q&A pairs from backend API"""
    
    def __init__(self, api_base_url: Optional[str] = None, 
                 mock_data_path: Optional[str] = None,
                 use_mock: bool = False,
                 auth_token: Optional[str] = None):
        """
        Initialize API client.
        
        Args:
            api_base_url: Base URL of the backend API (e.g., "https://api.example.com")
            mock_data_path: Path to mock JSON file (for development)
            use_mock: If True, use mock data instead of calling API
            auth_token: Bearer token for API authentication (optional)
        """
        self.api_base_url = api_base_url
        self.mock_data_path = mock_data_path
        self.use_mock = use_mock or (api_base_url is None)
        self.auth_token = auth_token
    
    def get_qa_pairs_by_user(self, user_id: str) -> List[Dict]:
        """
        Retrieve all Q&A pairs for a user from backend API.
        
        API Endpoint: GET {api_base_url}/api/questions/user/{user_id}
        
        Expected API Response Format:
        [
            {
                "question_id": "123",
                "question": "Why are you interested in backend development?",
                "answer": "I'm passionate about building scalable systems...",
                "job_title": "Backend Engineer",
                "company_name": "Google",
                "submission_date": "2024-01-15T10:30:00Z"
            },
            ...
        ]
        
        Returns:
            List of dicts with keys:
            - question_id: str
            - question: str
            - answer: str
            - job_title: str
            - company_name: str
            - submission_date: str (ISO format)
        """
        if self.use_mock:
            return self._load_mock_data(user_id)
        else:
            return self._fetch_from_api(user_id)
    
    def _fetch_from_api(self, user_id: str) -> List[Dict]:
        """Fetch Q&A pairs from backend API"""
        if not self.api_base_url:
            raise ValueError("API base URL not configured")
        
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library is required for API calls. Install it with: pip install requests")
        
        endpoint = f"{self.api_base_url}/api/questions/user/{user_id}"
        
        # Prepare headers with Bearer token if provided
        headers = {}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        try:
            response = requests.get(endpoint, headers=headers, timeout=30)
            response.raise_for_status()
            qa_pairs = response.json()
            
            # Validate response structure
            if not isinstance(qa_pairs, list):
                raise ValueError(f"API returned invalid format: expected list, got {type(qa_pairs)}")
            
            # Transform camelCase (from C# backend) to snake_case (Python convention)
            # Map: questionId -> question_id, jobTitle -> job_title, etc.
            transformed_pairs = []
            for item in qa_pairs:
                transformed_item = {
                    'question_id': item.get('questionId') or item.get('question_id'),
                    'question': item.get('question'),
                    'answer': item.get('answer'),
                    'job_title': item.get('jobTitle') or item.get('job_title'),
                    'company_name': item.get('companyName') or item.get('company_name'),
                    'submission_date': item.get('submissionDate') or item.get('submission_date'),
                }
                
                # Validate all required fields are present
                missing_fields = [k for k, v in transformed_item.items() if v is None]
                if missing_fields:
                    raise ValueError(f"API response missing required fields: {missing_fields}")
                
                transformed_pairs.append(transformed_item)
            
            return transformed_pairs
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to fetch Q&A pairs from API: {e}")
    
    def _load_mock_data(self, user_id: str) -> List[Dict]:
        """Load Q&A pairs from mock JSON file"""
        if not self.mock_data_path:
            raise ValueError("Mock data path not configured")
        
        mock_file = Path(self.mock_data_path)
        
        if not mock_file.exists():
            raise FileNotFoundError(f"Mock data file not found: {mock_file}")
        
        try:
            with open(mock_file, 'r', encoding='utf-8') as f:
                mock_data = json.load(f)
            
            # Mock data structure: flat list [ { question_id, question, answer, ... }, ... ]
            # In production, the API endpoint includes user_id in URL path, so backend filters by user
            # For mock data, we return all items (user filtering will be handled by backend API in production)
            if not isinstance(mock_data, list):
                raise ValueError(f"Invalid mock data format: expected list, got {type(mock_data)}")
            
            # Validate structure
            if mock_data and isinstance(mock_data[0], dict):
                required_fields = ['question_id', 'question', 'answer', 'job_title', 'company_name', 'submission_date']
                missing_fields = [field for field in required_fields if field not in mock_data[0]]
                if missing_fields:
                    raise ValueError(f"Mock data missing required fields: {missing_fields}")
            
            return mock_data
                
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in mock data file: {e}")

