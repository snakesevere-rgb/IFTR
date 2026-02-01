# In analyze_models.py or any terminal script:
import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Now imports should work
from app.models.order import Order

print(f"Python path: {sys.path[:2]}")

try:
    from app.models.order import Order
    print("✅ Order model exists")
    print(f"  Fields: {list(Order.model_fields.keys())}")
except ImportError as e:
    print(f"❌ Order model: {e}")
    import traceback
    traceback.print_exc()

# Check for surplus models
import os

surplus_files = []
for root, dirs, files in os.walk("app/models"):
    for file in files:
        if 'surplus' in file.lower():
            surplus_files.append(os.path.join(root, file))

if surplus_files:
    print(f"\nSurplus-related files: {surplus_files}")
else:
    print("\nNo surplus-specific files found")