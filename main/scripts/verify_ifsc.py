import sys
import os
import json

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from ifsc_utils import load_ifsc_table
    
    print("Loading table...")
    table = load_ifsc_table()
    print(f"Table loaded with {len(table)} entries.")
    
    # Check if json file exists in one of the possible paths
    possible_jsons = [
        'IFSC_CODES.json',
        os.path.join('uploads', 'IFSC_CODES.json'),
        os.path.join('instance', 'IFSC_CODES.json')
    ]
    
    found = False
    for p in possible_jsons:
        if os.path.exists(p):
            print(f"SUCCESS: JSON file created at {p}")
            found = True
            break
            
    if not found:
        # It might be that it loaded from excel but failed to save or saved elsewhere
        print("WARNING: JSON file not found in expected locations.")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
