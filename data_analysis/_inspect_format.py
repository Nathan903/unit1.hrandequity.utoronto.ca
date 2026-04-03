import json
nb = json.load(open('analysis.ipynb'))
print(f'Valid notebook: {len(nb["cells"])} cells, nbformat={nb["nbformat"]}')
