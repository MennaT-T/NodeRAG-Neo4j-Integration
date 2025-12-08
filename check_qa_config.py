import yaml

with open('POC_Data/documents/Node_config.yaml') as f:
    data = yaml.safe_load(f)
    
print('qa_api in config:', 'qa_api' in data)
print('qa_api value:', data.get('qa_api'))
print('enabled:', data.get('qa_api', {}).get('enabled', False))
